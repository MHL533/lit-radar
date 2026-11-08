-- 膜科研文献雷达：Supabase 数据库结构
-- 在 Supabase 控制台 → SQL Editor 里整段粘贴运行一次即可。

begin;

-- 用户资料：昵称和关注的研究方向（field 代码，见 papers.json 的 fields）
create table if not exists public.profiles (
  id uuid primary key references auth.users on delete cascade,
  nickname text not null default '',
  fields text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles: read own" on public.profiles;
create policy "profiles: read own" on public.profiles
  for select to authenticated using (auth.uid() = id);

drop policy if exists "profiles: insert own" on public.profiles;
create policy "profiles: insert own" on public.profiles
  for insert to authenticated with check (auth.uid() = id);

drop policy if exists "profiles: update own" on public.profiles;
create policy "profiles: update own" on public.profiles
  for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- 收藏与已读：每个用户一行一篇论文
create table if not exists public.marks (
  user_id uuid not null references auth.users on delete cascade,
  paper_id text not null,
  starred boolean not null default false,
  read boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key (user_id, paper_id)
);

alter table public.marks enable row level security;

drop policy if exists "marks: own rows" on public.marks;
create policy "marks: own rows" on public.marks
  for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 反馈：访客可匿名提交，登录用户的提交绑定本人的账户。网页只可写入反馈。
create table if not exists public.feedback (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  user_id uuid references auth.users on delete set null,
  type text not null default '其他',
  content text not null check (char_length(content) between 1 and 2000),
  contact text check (contact is null or char_length(contact) <= 100),
  paper_id text,
  page_url text
);

alter table public.feedback enable row level security;

drop policy if exists "feedback: anyone can submit" on public.feedback;
create policy "feedback: anyone can submit" on public.feedback
  for insert to anon, authenticated
  with check (user_id is not distinct from auth.uid());


-- 显式授权也适用于默认不向 Data API 开放新表的项目。
revoke all privileges on table public.profiles, public.marks, public.feedback from public, anon, authenticated;
grant usage on schema public to anon, authenticated;
grant select, insert, update on table public.profiles, public.marks to authenticated;
grant insert (user_id, type, content, contact, paper_id, page_url) on table public.feedback to anon, authenticated;

commit;
