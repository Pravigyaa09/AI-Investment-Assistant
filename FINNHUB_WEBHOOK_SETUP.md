# Finnhub Real-Time Webhook Setup

This guide explains how to set up Finnhub's webhook for real-time stock price updates.

## Overview

The webhook integration allows Finnhub to push real-time trade data directly to your backend, eliminating the need to poll for price updates. This provides:

- **Real-time updates**: Prices update immediately when trades occur
- **Reduced API calls**: No need to constantly poll for price data
- **Better rate limit management**: Finnhub pushes data to you instead of you requesting it
- **Lower latency**: Get updates as they happen

## Backend Setup

### 1. Webhook Endpoint

The webhook endpoint is already configured at:

```
POST /api/finnhub-webhook
```

### 2. Environment Configuration

The webhook secret has been added to `backend/.env`:

```env
FINNHUB_WEBHOOK_SECRET=d29mffpr01qvhsfu2mc0
CACHE_TTL_SECONDS=30
```

### 3. How It Works

1. **Finnhub sends webhook**: When a trade occurs for subscribed symbols, Finnhub sends a POST request to your webhook URL
2. **Authentication**: The request includes header `X-Finnhub-Secret: d29mffpr01qvhsfu2mc0`
3. **Cache update**: Your backend validates the secret and updates the price cache
4. **Frontend polls cache**: Your frontend continues polling every 10 seconds, but gets real-time data from the cache

### 4. Webhook Payload Format

Finnhub sends data in this format:

```json
{
  "data": [
    {
      "s": "AAPL",     // Symbol
      "p": 150.25,     // Price
      "t": 1234567890, // Unix timestamp (ms)
      "v": 100         // Volume
    }
  ],
  "type": "trade"
}
```

## Finnhub Dashboard Setup

### Step 1: Expose Your Local Backend (Development)

Since Finnhub needs to reach your webhook, you'll need to expose your local backend. Use one of these tools:

#### Option A: ngrok (Recommended)
```bash
# Install ngrok: https://ngrok.com/download
ngrok http 8000
```

This will give you a public URL like: `https://abc123.ngrok.io`

#### Option B: localtunnel
```bash
npm install -g localtunnel
lt --port 8000
```

#### Option C: Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

### Step 2: Configure Webhook in Finnhub Dashboard

1. **Go to Finnhub Dashboard**: https://finnhub.io/dashboard
2. **Navigate to Webhooks**: Click on "Webhooks" in the sidebar
3. **Create New Webhook**:
   - **URL**: `https://your-ngrok-url.ngrok.io/api/finnhub-webhook`
   - **Secret**: `d29mffpr01qvhsfu2mc0` (already in your .env)
   - **Event Type**: Select "Trade" events

4. **Subscribe to Symbols**:
   - Add symbols you want to track: `AAPL`, `MSFT`, `TSLA`, etc.
   - You can subscribe to any symbols you're actively trading

### Step 3: Test the Webhook

1. **Start your backend**:
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **Start ngrok** (in another terminal):
   ```bash
   ngrok http 8000
   ```

3. **Update Finnhub webhook URL** with your ngrok URL

4. **Test with curl**:
   ```bash
   curl -X POST https://your-ngrok-url.ngrok.io/api/finnhub-webhook \
     -H "X-Finnhub-Secret: d29mffpr01qvhsfu2mc0" \
     -H "Content-Type: application/json" \
     -d '{
       "data": [
         {"s": "AAPL", "p": 150.25, "t": 1234567890, "v": 100}
       ],
       "type": "trade"
     }'
   ```

5. **Check backend logs**: You should see:
   ```
   INFO: Received webhook: {...}
   INFO: Updated AAPL price to $150.25 from webhook
   INFO: Cache updated from webhook: AAPL = $150.25
   ```

## Frontend Integration

The frontend continues to work as before:

1. User enables "Auto-refresh (10s)" on Trading page
2. Frontend polls `/api/price` every 10 seconds
3. Backend returns cached price (updated by webhook)
4. User sees real-time price with "Last updated" timestamp

## Production Deployment

For production, you'll need to:

1. **Deploy backend** to a public server (AWS, Heroku, DigitalOcean, etc.)
2. **Get production URL**: e.g., `https://api.yourdomain.com`
3. **Update Finnhub webhook**: Point to `https://api.yourdomain.com/api/finnhub-webhook`
4. **Use HTTPS**: Finnhub requires HTTPS for webhooks

## Monitoring

### Check Webhook Status

View logs to see webhook activity:
```bash
tail -f backend/logs/app.log | grep webhook
```

### Verify Cache Updates

Check if prices are being updated:
```bash
curl http://localhost:8000/api/price?ticker=AAPL
```

### Debug Issues

If webhooks aren't working:

1. **Check secret**: Verify `FINNHUB_WEBHOOK_SECRET` in `.env` matches Finnhub dashboard
2. **Check URL**: Make sure ngrok/tunnel is running and URL is correct
3. **Check logs**: Look for errors in backend logs
4. **Test manually**: Use curl to send test webhook payload

## Rate Limits

With webhooks:
- **No polling to Finnhub**: Webhook pushes data to you
- **Cache TTL**: 30 seconds (configurable via `CACHE_TTL_SECONDS`)
- **Frontend polling**: Every 10 seconds (gets cached data)

This setup is much more efficient than pure polling and stays within Finnhub's free tier limits.

## Troubleshooting

### Webhook Not Received

1. Check ngrok is running: `curl https://your-url.ngrok.io`
2. Check backend is running: `curl http://localhost:8000/health`
3. Check Finnhub dashboard for webhook status
4. Verify secret matches in both places

### Price Not Updating in Frontend

1. Check backend cache: Look for "Cache updated from webhook" in logs
2. Check frontend timestamp: Should update every 10 seconds
3. Verify ticker is subscribed in Finnhub webhook settings

### Authentication Failed

1. Verify `X-Finnhub-Secret` header is being sent
2. Check secret matches in `.env` file
3. Restart backend after changing `.env`

## Next Steps

1. **Test the webhook** with curl command above
2. **Subscribe to more symbols** in Finnhub dashboard
3. **Monitor logs** to see real-time updates
4. **Check Trading page** to see timestamp updating every 10 seconds

## Support

- Finnhub Docs: https://finnhub.io/docs/api/webhook
- ngrok Docs: https://ngrok.com/docs
