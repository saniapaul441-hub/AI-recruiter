# AI Recruiter - Vercel Deployment Guide

This guide describes how to deploy the AI Recruiter web application (Node.js Express backend and static frontend dashboard) to Vercel.

---

## 🔑 Required Environment Variables

You must configure the following environment variables in your Vercel Project Dashboard under **Settings** -> **Environment Variables**:

| Variable Name | Required | Description |
|---|---|---|
| `SUPABASE_URL` | **Yes** | Your Supabase Project URL (e.g. `https://xyz.supabase.co`). |
| `SUPABASE_KEY` | **Yes** | Your Supabase API Public or Service Role Key. |
| `ANTHROPIC_API_KEY` | **Yes** | Anthropic API Key (for Claude 3.5 Sonnet) used for JD deconstruction, resume parsing, candidate evaluation, and coaching feedback generation. |
| `JWT_SECRET` | **Yes** | A long, secure random string used to sign JWT authentication tokens (e.g., `openssl rand -hex 32` or any random password). |

---

## 🚀 Deployment Options

### Option A: Using the Vercel Dashboard (GitHub Integration - Recommended)

1. Push your local workspace changes to a Git repository (GitHub, GitLab, or Bitbucket).
2. Go to the [Vercel Dashboard](https://vercel.com/dashboard) and click **Add New** -> **Project**.
3. Select your repository and import it.
4. Expand **Environment Variables** and add the keys listed above.
5. Click **Deploy**. Vercel will automatically build the serverless functions and serve the frontend assets.

### Option B: Using the Vercel CLI (Command Line)

If you have the Vercel CLI installed on your machine, you can deploy directly from your terminal:

1. Open your terminal in the project root directory.
2. Run the login command if you haven't already:
   ```bash
   vercel login
   ```
3. Deploy the project:
   ```bash
   vercel
   ```
4. Follow the command-line prompts to configure your project.
5. Set your environment variables in the Vercel Dashboard, or use the CLI command:
   ```bash
   vercel env add SUPABASE_URL <value>
   vercel env add SUPABASE_KEY <value>
   vercel env add ANTHROPIC_API_KEY <value>
   vercel env add JWT_SECRET <value>
   ```
6. To push the changes live (Production deployment):
   ```bash
   vercel --prod
   ```

---

## 📂 Pre-seeded Credentials

Once deployed, access your Vercel deployment URL (e.g. `https://your-project.vercel.app/`).
You can sign in using the following pre-seeded credentials:

*   **Recruiter Portal**: `recruiter@recruiter.com` / Password: `recruiter123`
*   **Admin Dashboard**: `admin@admin.com` / Password: `admin123`

*(Note: These credentials will function once your Supabase database is connected and initialized with `supabase_schema.sql`).*
