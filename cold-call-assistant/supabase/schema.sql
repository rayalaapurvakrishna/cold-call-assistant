-- CallGuide schema. Run once in the Supabase SQL Editor.
create extension if not exists pgcrypto;

create table if not exists public.calls (
  id uuid primary key default gen_random_uuid(),
  prospect_name text not null default '',
  company_name text not null default '',
  role text not null default '',
  phone_note text not null default '',
  stage_reached integer not null default 1 check (stage_reached between 1 and 8),
  outcome text not null default 'in_progress',
  final_note text not null default '',
  last_prospect_words text not null default '',
  created_at timestamptz not null default now(),
  closed_at timestamptz
);

create table if not exists public.call_stages (
  id uuid primary key default gen_random_uuid(),
  call_id uuid not null references public.calls(id) on delete cascade,
  stage_number integer not null check (stage_number between 1 and 8),
  actions jsonb not null default '[]'::jsonb,
  prospect_words text not null default '',
  caller_note text not null default '',
  created_at timestamptz not null default now(),
  unique (call_id, stage_number)
);

create index if not exists calls_created_at_idx on public.calls(created_at desc);
create index if not exists calls_outcome_idx on public.calls(outcome);
create index if not exists call_stages_call_id_idx on public.call_stages(call_id);

-- The backend uses the service-role key. Keep it ONLY in Render's environment.
-- Do not expose it in VITE_* variables or browser code.
-- For a multi-user production rollout, add Supabase Auth and per-user RLS policies.

-- Atomic writes: stage data and call progress are committed together.
create or replace function public.save_call_stage_atomic(
  p_call_id uuid,
  p_stage_number integer,
  p_stage_reached integer,
  p_actions jsonb,
  p_prospect_words text,
  p_caller_note text
) returns void
language plpgsql
as $$
declare
  affected integer;
begin
  insert into public.call_stages (call_id, stage_number, actions, prospect_words, caller_note)
  values (p_call_id, p_stage_number, coalesce(p_actions, '[]'::jsonb), coalesce(p_prospect_words, ''), coalesce(p_caller_note, ''))
  on conflict (call_id, stage_number) do update set
    actions = excluded.actions,
    prospect_words = excluded.prospect_words,
    caller_note = excluded.caller_note,
    created_at = now();

  update public.calls
  set stage_reached = greatest(stage_reached, p_stage_reached)
  where id = p_call_id;
  get diagnostics affected = row_count;
  if affected = 0 then raise exception 'Call not found'; end if;
end;
$$;

create or replace function public.close_call_atomic(
  p_call_id uuid,
  p_outcome text,
  p_final_note text,
  p_current_stage integer,
  p_stage_reached integer,
  p_prospect_words text,
  p_actions jsonb,
  p_caller_note text
) returns public.calls
language plpgsql
as $$
declare
  saved_call public.calls;
begin
  insert into public.call_stages (call_id, stage_number, actions, prospect_words, caller_note)
  values (p_call_id, p_current_stage, coalesce(p_actions, '[]'::jsonb), coalesce(p_prospect_words, ''), coalesce(p_caller_note, ''))
  on conflict (call_id, stage_number) do update set
    actions = excluded.actions,
    prospect_words = excluded.prospect_words,
    caller_note = excluded.caller_note,
    created_at = now();

  update public.calls
  set outcome = p_outcome,
      final_note = coalesce(p_final_note, ''),
      stage_reached = greatest(stage_reached, p_stage_reached, p_current_stage),
      last_prospect_words = coalesce(p_prospect_words, ''),
      closed_at = now()
  where id = p_call_id
  returning * into saved_call;

  if not found then raise exception 'Call not found'; end if;
  return saved_call;
end;
$$;

revoke all on function public.save_call_stage_atomic(uuid, integer, integer, jsonb, text, text) from public;
revoke all on function public.close_call_atomic(uuid, text, text, integer, integer, text, jsonb, text) from public;
grant execute on function public.save_call_stage_atomic(uuid, integer, integer, jsonb, text, text) to service_role;
grant execute on function public.close_call_atomic(uuid, text, text, integer, integer, text, jsonb, text) to service_role;

-- Lock browser/anon access. The backend service-role key bypasses RLS and never reaches the browser.
alter table public.calls enable row level security;
alter table public.call_stages enable row level security;
