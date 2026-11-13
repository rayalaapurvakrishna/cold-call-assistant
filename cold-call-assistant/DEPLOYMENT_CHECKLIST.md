# Deployment checklist

## Supabase
- [ ] Create project.
- [ ] Run `supabase/schema.sql` completely.
- [ ] Confirm `calls`, `call_stages`, `save_call_stage_atomic`, and `close_call_atomic` exist.
- [ ] Copy Project URL and service-role key privately.

## Render
- [ ] New Web Service from GitHub.
- [ ] Root: `backend`.
- [ ] Build: `pip install -r requirements.txt`.
- [ ] Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- [ ] Environment variables set.
- [ ] Health path `/health` returns HTTP 200.

## Vercel
- [ ] Import GitHub repo.
- [ ] Root: `frontend`.
- [ ] Build: `npm run build`.
- [ ] Output: `dist`.
- [ ] `VITE_API_URL` points to Render base URL.
- [ ] Frontend opens without console errors.

## End-to-end verification
- [ ] Start a call.
- [ ] Save stage 1 and stage 2.
- [ ] Navigate backward; confirm drafts remain.
- [ ] End early at stage 2; confirm stage 2 notes are saved.
- [ ] Refresh frontend; call remains in history.
- [ ] Open call detail; exact prospect words appear.
- [ ] Confirm a report request does not become `next_step_agreed` automatically.
- [ ] Confirm `do_not_call` is available.
- [ ] Test Gemini stage coach and note structuring.
- [ ] Verify browser source/network does not contain the Supabase service-role key or Gemini key.
