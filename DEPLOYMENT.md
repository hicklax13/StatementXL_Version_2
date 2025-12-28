# Deployment Guide

## Overview

StatementXL uses a two-service deployment architecture:

- **Backend**: Railway (Python/FastAPI)
- **Frontend**: Vercel (React/Vite)

---

## Environment Variables

### Required for Backend (Railway)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host/db` |
| `GOOGLE_API_KEY` | Gemini AI API key | `AIza...` |
| `STRIPE_SECRET_KEY` | Stripe secret key | `sk_live_...` or `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | `whsec_...` |
| `STRIPE_PRO_PRICE_ID` | Stripe price ID for Pro plan | `price_1...` |
| `STRIPE_ENTERPRISE_PRICE_ID` | Stripe price ID for Enterprise | `price_1...` |
| `SECRET_KEY` | JWT secret key | Random 32+ char string |
| `ALLOWED_ORIGINS` | CORS allowed origins | `https://statementxl.com` |

### Required for Frontend (Vercel)

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `https://your-app.up.railway.app/api/v1` |
| `VITE_STRIPE_PUBLIC_KEY` | Stripe publishable key | `pk_live_...` or `pk_test_...` |

---

## Railway Deployment

### 1. Create Railway Project

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init
```

### 2. Add PostgreSQL

```bash
railway add --database postgresql
```

### 3. Set Environment Variables

```bash
railway variables set GOOGLE_API_KEY=your_key
railway variables set STRIPE_SECRET_KEY=sk_test_xxx
railway variables set SECRET_KEY=$(openssl rand -hex 32)
```

### 4. Deploy

```bash
railway up
```

---

## Vercel Deployment

### 1. Install Vercel CLI

```bash
npm install -g vercel
```

### 2. Deploy Frontend

```bash
cd frontend
vercel
```

### 3. Set Environment Variables

In Vercel dashboard, add:

- `VITE_API_URL` = Your Railway backend URL

### 4. Update vercel.json

Update the API rewrite destination to your Railway URL:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-railway-app.up.railway.app/api/:path*"
    }
  ]
}
```

---

## Stripe Setup

### 1. Create Stripe Products

In Stripe Dashboard → Products:

1. **Pro Plan** ($19/month)
   - Create product "StatementXL Pro"
   - Add monthly price
   - Copy price ID → `STRIPE_PRO_PRICE_ID`

2. **Enterprise Plan** ($49/month)
   - Create product "StatementXL Enterprise"
   - Add monthly price
   - Copy price ID → `STRIPE_ENTERPRISE_PRICE_ID`

### 2. Configure Webhook

In Stripe Dashboard → Webhooks:

1. Add endpoint: `https://your-railway-app.up.railway.app/api/v1/payments/webhook`
2. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
3. Copy signing secret → `STRIPE_WEBHOOK_SECRET`

---

## Health Check URLs

- Backend: `https://your-app.up.railway.app/health`
- API Docs: `https://your-app.up.railway.app/docs`
- Frontend: `https://your-vercel-app.vercel.app`
