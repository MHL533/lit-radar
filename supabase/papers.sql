-- 科研文献查询器：全库文献表与检索函数（在 Supabase → SQL Editor 里整段运行一次；以后升级也可重复运行）
-- 文献由 GitHub Actions（scripts/sync_db.py，用 service_role 密钥）写入；网页用公开 anon 密钥只读查询。
-- 全文检索用 PGroonga，中英文混合检索都能用索引。

create extension if not exists pgroonga;

create table if not exists public.papers (
  id            text primary key,           -- 由 DOI 生成，与网页、收藏表 marks.paper_id 一致
  doi           text not null,
  title         text not null,
  title_zh      text,
  journal       text not null,
  journal_abbr  text,
  cas_zone      smallint,                   -- 中科院 2025 大类分区：1 / 2
  impact_factor real,                       -- JCR 2025
  published     date not null,
  fields        text[] not null default '{}',
  groups        text[] not null default '{}',
  keywords      text[] not null default '{}',
  keywords_zh   text[] not null default '{}',
  authors       text[] not null default '{}',
  author_count  integer,
  affils        text[] not null default '{}',
  corr_affils   text[] not null default '{}',
  first_affil   text,
  summary_zh    text,
  is_key        boolean not null default false,
  has_abstract  boolean not null default false,
  added         timestamptz,
  synced_at     timestamptz not null default now()
);

alter table public.papers enable row level security;
drop policy if exists "papers: public read" on public.papers;
create policy "papers: public read" on public.papers for select to anon, authenticated using (true);

create index if not exists papers_published on public.papers (published desc, id);
create index if not exists papers_groups on public.papers using gin (groups);
create index if not exists papers_fields on public.papers using gin (fields);
create index if not exists papers_journal on public.papers (journal);
create index if not exists papers_if on public.papers (impact_factor desc nulls last);
create index if not exists papers_affil on public.papers (first_affil);
create index if not exists papers_text on public.papers using pgroonga (title, title_zh, keywords, keywords_zh, authors);

-- 共用的筛选条件
-- 检索函数用动态 SQL：只拼接实际用到的条件，PostgreSQL 才能用上各列索引（日期、领域 GIN、PGroonga 全文）。
drop function if exists public.search_papers(text[], text[], date, date, text, smallint, text, text, boolean, boolean, boolean, text, integer, integer, integer);
drop function if exists public.paper_facets(text[], text[], date, date, text, smallint, text, text, boolean, boolean, boolean, integer);
drop function if exists public.paper_filter(public.papers, text[], text[], date, date, text, smallint, text, text, boolean, boolean, boolean);
drop function if exists public.paper_filter(public.papers, text[], text[], date, date, text, smallint, text, boolean, text[], text[]);

-- 由筛选参数生成 WHERE 子句（参数在 EXECUTE ... USING 中依次为 $1..$11）
create or replace function public.paper_where(
  p_groups text[], p_fields text[], p_since date, p_until date, p_journal text, p_zone smallint,
  p_inst text, p_q text, p_key boolean, p_ids text[], p_not_ids text[])
returns text language plpgsql immutable as $$
declare w text[] := array['true'];
begin
  if p_groups is not null then w := array_append(w, 'p.groups && $1'::text); end if;
  if p_fields is not null then w := array_append(w, 'p.fields && $2'::text); end if;
  if p_since is not null then w := array_append(w, 'p.published >= $3'::text); end if;
  if p_until is not null then w := array_append(w, 'p.published <= $4'::text); end if;
  if p_journal is not null then w := array_append(w, 'p.journal = $5'::text); end if;
  if p_zone is not null then w := array_append(w, 'p.cas_zone = $6'::text); end if;
  if coalesce(p_inst, '') <> '' then w := array_append(w, $w$exists (select 1 from unnest(p.affils) a where a ilike '%' || $7 || '%')$w$::text); end if;
  if coalesce(p_q, '') <> '' then
    w := array_append(w, '(p.title &@~ pgroonga_query_escape($8) or p.title_zh &@~ pgroonga_query_escape($8) or p.keywords &@~ pgroonga_query_escape($8)'
              ' or p.keywords_zh &@~ pgroonga_query_escape($8) or p.authors &@~ pgroonga_query_escape($8) or p.doi = lower($8))'::text);
  end if;
  if coalesce(p_key, false) then w := array_append(w, 'p.is_key'::text); end if;
  if p_ids is not null then w := array_append(w, 'p.id = any($10)'::text); end if;
  if p_not_ids is not null then w := array_append(w, 'not (p.id = any($11))'::text); end if;
  return array_to_string(w, ' and ');
end $$;

-- 列表：筛选 + 全文检索 + 排序 + 分页，附带筛出总数
create or replace function public.search_papers(
  p_groups text[] default null, p_fields text[] default null, p_since date default null, p_until date default null,
  p_journal text default null, p_zone smallint default null, p_inst text default null, p_q text default null,
  p_key boolean default false, p_ids text[] default null, p_not_ids text[] default null,
  p_sort text default 'date', p_dir integer default -1, p_limit integer default 60, p_offset integer default 0)
returns table (paper jsonb, total bigint)
language plpgsql stable as $$
declare
  w text := public.paper_where(p_groups, p_fields, p_since, p_until, p_journal, p_zone, p_inst, p_q, p_key, p_ids, p_not_ids);
  ord text := case
    when p_sort = 'if' and p_dir < 0 then 'p.impact_factor desc nulls last, p.published desc, p.id'
    when p_sort = 'if' then 'p.impact_factor asc nulls last, p.published desc, p.id'
    when p_sort = 'inst' and p_dir > 0 then 'p.first_affil asc nulls last, p.published desc, p.id'
    when p_sort = 'inst' then 'p.first_affil desc nulls last, p.published desc, p.id'
    when p_dir > 0 then 'p.published asc, p.id'
    else 'p.published desc, p.id' end;
  n bigint;
begin
  execute 'select count(*) from public.papers p where ' || w into n
    using p_groups, p_fields, p_since, p_until, p_journal, p_zone, p_inst, p_q, p_key, p_ids, p_not_ids;
  return query execute 'select to_jsonb(p) - ''synced_at'', $12 from public.papers p where ' || w || ' order by ' || ord || ' limit $13 offset $14'
    using p_groups, p_fields, p_since, p_until, p_journal, p_zone, p_inst, p_q, p_key, p_ids, p_not_ids, n,
          least(greatest(p_limit, 1), 5000), greatest(p_offset, 0);
end $$;

-- 统计、趋势、排行与关联图样本（同一组筛选条件）
create or replace function public.paper_facets(
  p_groups text[] default null, p_fields text[] default null, p_since date default null, p_until date default null,
  p_journal text default null, p_zone smallint default null, p_inst text default null, p_q text default null,
  p_key boolean default false, p_ids text[] default null, p_not_ids text[] default null, p_sample integer default 0)
returns jsonb
language plpgsql stable as $$
declare
  w text := public.paper_where(p_groups, p_fields, p_since, p_until, p_journal, p_zone, p_inst, p_q, p_key, p_ids, p_not_ids);
  r jsonb;
begin
  execute 'with hits as materialized (select p.published, p.cas_zone, p.is_key, p.fields, p.journal, p.affils, p.keywords, p.keywords_zh, p.journal_abbr
             from public.papers p where ' || w || ')
  select jsonb_build_object(
    ''total'',  (select count(*) from hits),
    ''week'',   (select count(*) from hits where published >= current_date - 7),
    ''zone1'',  (select count(*) from hits where cas_zone = 1),
    ''key'',    (select count(*) from hits where is_key),
    ''months'', (select coalesce(jsonb_object_agg(m, c), ''{}'') from (select to_char(published, ''YYYY-MM'') m, count(*) c from hits group by 1) x),
    ''fields'', (select coalesce(jsonb_agg(jsonb_build_array(f, c) order by c desc), ''[]'') from (select f, count(*) c from hits, unnest(fields) f group by f order by c desc limit 40) x),
    ''journals'', (select coalesce(jsonb_agg(jsonb_build_array(journal, c) order by c desc), ''[]'') from (select journal, count(*) c from hits group by journal order by c desc limit 60) x),
    ''insts'',  (select coalesce(jsonb_agg(jsonb_build_array(a, c) order by c desc), ''[]'') from (select a, count(*) c from hits, unnest(affils) a group by a order by c desc limit 40) x),
    ''keywords'', (select coalesce(jsonb_agg(jsonb_build_array(k, z, c) order by c desc), ''[]'') from (
        select k, max(z) z, count(*) c from hits, unnest(keywords, keywords_zh) as u(k, z) group by k order by c desc limit 40) x),
    ''sample'', case when $12 > 0 then (select coalesce(jsonb_agg(jsonb_build_array(fields, keywords, keywords_zh, affils[1:4], journal_abbr)), ''[]'')
        from (select * from hits order by published desc limit least($12, 6000)) s) else ''[]''::jsonb end)'
  into r
  using p_groups, p_fields, p_since, p_until, p_journal, p_zone, p_inst, p_q, p_key, p_ids, p_not_ids, p_sample;
  return r;
end $$;

-- 各领域每月篇数：由同步脚本在每次写入后刷新，查询时直接读汇总表
create table if not exists public.paper_month_counts (grp text not null, month text not null, n integer not null, primary key (grp, month));
alter table public.paper_month_counts enable row level security;
drop policy if exists "paper_month_counts: public read" on public.paper_month_counts;
create policy "paper_month_counts: public read" on public.paper_month_counts for select to anon, authenticated using (true);

create or replace function public.refresh_paper_counts() returns void language sql security definer set search_path = public as $$
  delete from public.paper_month_counts;
  insert into public.paper_month_counts
    select g, to_char(published, 'YYYY-MM'), count(*) from public.papers, unnest(groups) g group by 1, 2
    union all
    select '*', to_char(published, 'YYYY-MM'), count(*) from public.papers group by 2;
$$;
revoke execute on function public.refresh_paper_counts() from public, anon, authenticated;

drop function if exists public.paper_months(text[]);
create or replace function public.paper_months(p_groups text[] default null)
returns table (month text, n bigint)
language sql stable as $$
  select month, sum(n)::bigint from public.paper_month_counts
  where (p_groups is null and grp = '*') or grp = any(p_groups) group by month order by month desc
$$;

grant execute on function public.search_papers, public.paper_facets, public.paper_months, public.paper_where to anon, authenticated;

-- 匿名访问的语句超时默认 3 秒，聚合统计放宽到 10 秒
alter role anon set statement_timeout = '10s';
alter role authenticated set statement_timeout = '10s';
notify pgrst, 'reload config';
select public.refresh_paper_counts();
