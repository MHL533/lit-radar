-- 膜科研文献雷达：Supabase 数据库结构
-- 在 Supabase 控制台 → SQL Editor 里整段粘贴运行一次即可。

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
  for select using (auth.uid() = id);

drop policy if exists "profiles: insert own" on public.profiles;
create policy "profiles: insert own" on public.profiles
  for insert with check (auth.uid() = id);

drop policy if exists "profiles: update own" on public.profiles;
create policy "profiles: update own" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

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
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 反馈：任何访客都可以提交；没有读取策略，只有你在 Supabase 控制台（Table Editor → feedback）里能看到
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
  with check (user_id is null or user_id = auth.uid());
