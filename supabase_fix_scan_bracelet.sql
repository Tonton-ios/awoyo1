-- AWOYO - Correctif fonction scan_bracelet
-- A coller dans Supabase > SQL Editor, puis Run.
-- Corrige l'erreur:
-- "column bracelet_uid is of type uuid but expression is of type text"

drop function if exists public.scan_bracelet(text, text);

create or replace function public.scan_bracelet(
  p_token text,
  p_staff_id text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid;
  v_bracelet record;
begin
  begin
    v_uid := split_part(trim(p_token), ':', 1)::uuid;
  exception when others then
    begin
      insert into public.scan_logs (bracelet_uid, status, scanned_by)
      values (null, 'INVALID', p_staff_id);
    exception when others then
      null;
    end;

    return jsonb_build_object(
      'status', 'INVALID',
      'message', 'Format QR invalide',
      'bracelet_num', null
    );
  end;

  select *
  into v_bracelet
  from public.bracelets
  where uid = v_uid
    and token = trim(p_token)
  for update;

  if not found then
    begin
      insert into public.scan_logs (bracelet_uid, status, scanned_by)
      values (v_uid, 'INVALID', p_staff_id);
    exception when others then
      null;
    end;

    return jsonb_build_object(
      'status', 'INVALID',
      'message', 'QR code non reconnu',
      'bracelet_num', null
    );
  end if;

  if v_bracelet.scanned then
    begin
      insert into public.scan_logs (bracelet_uid, status, scanned_by)
      values (v_uid, 'DUPLICATE', p_staff_id);
    exception when others then
      null;
    end;

    return jsonb_build_object(
      'status', 'DUPLICATE',
      'message', 'Bracelet deja scanne',
      'bracelet_num', v_bracelet.bracelet_num,
      'first_scan_at', v_bracelet.scanned_at
    );
  end if;

  update public.bracelets
  set scanned = true,
      scanned_at = now(),
      scanned_by = p_staff_id
  where uid = v_uid;

  begin
    insert into public.scan_logs (bracelet_uid, status, scanned_by)
    values (v_uid, 'VALID', p_staff_id);
  exception when others then
    null;
  end;

  return jsonb_build_object(
    'status', 'VALID',
    'message', 'Acces autorise',
    'bracelet_num', v_bracelet.bracelet_num,
    'first_scan_at', null
  );
end;
$$;
