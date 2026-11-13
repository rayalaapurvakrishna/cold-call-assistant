# Push CallGuide to GitHub (Windows PowerShell)

1. Download and extract `cold-call-assistant-starter.zip`.
2. Open the extracted `cold-call-assistant` folder.
3. In File Explorer, click the address bar, type `powershell`, and press Enter.
4. Run these commands one at a time:

```powershell
git init
git add .
git status
git commit -m "Build CallGuide cold-call assistant"
git branch -M main
```

5. On GitHub, create a new **empty public repository** named `cold-call-assistant`. Do not add a README, license, or .gitignore there because this project already contains them.
6. Copy the repository HTTPS URL. It looks like `https://github.com/YOUR-USERNAME/cold-call-assistant.git`.
7. Back in PowerShell, run (replace the URL with your own):

```powershell
git remote add origin https://github.com/YOUR-USERNAME/cold-call-assistant.git
git push -u origin main
```

8. Open the GitHub repository in your browser and confirm that `frontend`, `backend`, `supabase`, `README.md`, and `DEMO_SCRIPT.md` are visible.

**Security check before pushing:** never create `backend/.env` in the project folder before pushing. Only edit `.env` locally after extracting, and confirm it is ignored by `.gitignore`. The only committed environment file should be `backend/.env.example`, which contains placeholders.
