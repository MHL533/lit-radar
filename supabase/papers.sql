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
create or replace function public.paper_filter(
  p public.papers, p_groups text[], p_fields text[], p_since date, p_until date, p_journal text, p_zone smallint,
  p_inst text, p_q text, p_key boolean, p_star boolean, p_unread boolean)
returns boolean language sql stable as $$
  select (p_groups is null or p.groups && p_groups)
    and (p_fields is null or p.fields && p_fields)
    and (p_since is null or p.published >= p_since)
    and (p_until is null or p.published <= p_until)
    and (p_journal is null or p.journal = p_journal)
    and (p_zone is null or p.cas_zone = p_zone)
    and (p_inst is null or exists (select 1 from unnest(p.affils) a where a ilike '%' || p_inst || '%'))
    and (not coalesce(p_key, false) or p.is_key)
    and (not coalesce(p_star, false) or exists (select 1 from public.marks m where m.user_id = auth.uid() and m.paper_id = p.id and m.starred))
    and (not coalesce(p_unread, false) or not exists (select 1 from public.marks m where m.user_id = auth.uid() and m.paper_id = p.id and m.read))
$$;

-- 列表：筛选 + 全文检索 + 排序 + 分页，附带筛出总数
create or replace function public.search_papers(
  p_groups text[] default null, p_fields text[] default null, p_since date default null, p_until date default null,
  p_journal text default null, p_zone smallint default null, p_inst text default null, p_q text default null,
  p_key boolean default false, p_star boolean default false, p_unread boolean default false,
  p_sort text default 'date', p_dir integer default -1, p_limit integer default 60, p_offset integer default 0)
returns table (paper jsonb, total bigint)
language sql stable as $$
  with hits as (
    select p.* from public.papers p
    where (p_q is null or p_q = '' or p.title &@~ pgroonga_query_escape(p_q) or p.title_zh &@~ pgroonga_query_escape(p_q) or p.keywords &@~ pgroonga_query_escape(p_q) or p.keywords_zh &@~ pgroonga_query_escape(p_q) or p.authors &@~ pgroonga_query_escape(p_q)
           or p.doi = lower(p_q))
      and public.paper_filter(p, p_groups, p_fields, p_since, p_until, p_journal, p_zone, p_inst, p_q, p_key, p_star, p_unread)
  )
  select to_jsonb(h) - 'synced_at', count(*) over ()
  from hits h
  order by
    case when p_sort = 'if'   and p_dir < 0 then h.impact_factor end desc nulls last,
    case when p_sort = 'if'   and p_dir > 0 then h.impact_factor end asc nulls last,
    case when p_sort = 'inst' and p_dir > 0 then h.first_affil end asc nulls last,
    case when p_sort = 'inst' and p_dir < 0 then h.first_affil end desc nulls last,
    case when p_sort = 'date' and p_dir > 0 then h.published end asc,
    h.published desc, h.id
  limit least(greatest(p_limit, 1), 5000) offset greatest(p_offset, 0)
$$;

-- 统计、趋势、排行与关联图样本（同一组筛选条件）
create or replace function public.paper_facets(
  p_groups text[] default null, p_fields text[] default null, p_since date default null, p_until date default null,
  p_journal text default null, p_zone smallint default null, p_inst text default null, p_q text default null,
  p_key boolean default false, p_star boolean default false, p_unread boolean default false, p_sample integer default 0)
returns jsonb
language sql stable as $$
  with hits as (
    select p.* from public.papers p
    where (p_q is null or p_q = '' or p.title &@~ pgroonga_query_escape(p_q) or p.title_zh &@~ pgroonga_query_escape(p_q) or p.keywords &@~ pgroonga_query_escape(p_q) or p.keywords_zh &@~ pgroonga_query_escape(p_q) or p.authors &@~ pgroonga_query_escape(p_q)
           or p.doi = lower(p_q))
      and public.paper_filter(p, p_groups, p_fields, p_since, p_until, p_journal, p_zone, p_inst, p_q, p_key, p_star, p_unread)
  )
  select jsonb_build_object(
    'total',  (select count(*) from hits),
    'week',   (select count(*) from hits where published >= current_date - 7),
    'zone1',  (select count(*) from hits where cas_zone = 1),
    'key',    (select count(*) from hits where is_key),
    'months', (select coalesce(jsonb_object_agg(m, n), '{}') from (select to_char(published, 'YYYY-MM') m, count(*) n from hits group by 1) x),
    'fields', (select coalesce(jsonb_agg(jsonb_build_array(f, n) order by n desc), '[]') from (select f, count(*) n from hits, unnest(fields) f group by f order by n desc limit 40) x),
    'journals', (select coalesce(jsonb_agg(jsonb_build_array(journal, n) order by n desc), '[]') from (select journal, count(*) n from hits group by journal order by n desc limit 60) x),
    'insts',  (select coalesce(jsonb_agg(jsonb_build_array(a, n) order by n desc), '[]') from (select a, count(*) n from hits, unnest(affils) a group by a order by n desc limit 40) x),
    'keywords', (select coalesce(jsonb_agg(jsonb_build_array(k, z, n) order by n desc), '[]') from (
        select k, max(z) z, count(*) n from hits, unnest(keywords, keywords_zh) as u(k, z) group by k order by n desc limit 40) x),
    'sample', case when p_sample > 0 then (select coalesce(jsonb_agg(jsonb_build_array(fields, keywords, keywords_zh, affils[1:4], journal_abbr)), '[]')
        from (select * from hits order by published desc limit least(p_sample, 6000)) s) else '[]'::jsonb end
  )
$$;

-- 各领域每月篇数（网页“按年 / 月”下拉框用）
create or replace function public.paper_months(p_groups text[] default null)
returns table (month text, n bigint)
language sql stable as $$
  select to_char(published, 'YYYY-MM'), count(*) from public.papers
  where p_groups is null or groups && p_groups group by 1 order by 1 desc
$$;

grant execute on function public.search_papers, public.paper_facets, public.paper_months, public.paper_filter to anon, authenticated;
