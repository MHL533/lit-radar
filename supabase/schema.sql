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
