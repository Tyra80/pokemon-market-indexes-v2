# Pokémon Market Indexes - Dashboard

Web dashboard for visualizing the Pokémon Market Indexes.

## Setup

```bash
cd dashboard
npm install
```

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Production Build

```bash
npm run build
npm start
```

## Deployment on Vercel

1. Connect your GitHub repo to Vercel
2. Set **Root Directory** to `dashboard`
3. Vercel will auto-detect Next.js and deploy

## Environment Variables (for Supabase connection)

Create a `.env.local` file:

```
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

## Tech Stack

- **Framework**: Next.js 14
- **Charts**: Recharts
- **Styling**: CSS-in-JS

## Features

- 📈 Daily index values (RARE_100, RARE_500, RARE_ALL)
- 📋 Index constituents with filtering
- 🔍 Individual card details with price history
- 📖 Full methodology documentation
- 🔗 External links to TCGPlayer
