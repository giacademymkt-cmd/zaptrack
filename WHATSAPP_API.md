# 📞 API Routes for WhatsApp Link Generation and Redirect with Pixel

## POST /api/generate-link

Generate WhatsApp tracking link with fbclid

**Request:**
```json
{
  "phone": "5511999999999",
  "message": "Olá! Vi seu anúncio e tenho interesse"
}
```

**Response:**
```json
{
  "success": true,
  "fbclid": "abc123xyz",
  "tracking_url": "https://zaptrack.onrender.com/r/abc123xyz",
  "final_url": "https://wa.me/5511999999999?text=Olá!+Vi+seu+anúncio..."
}
```

## GET /r/<fbclid>

Fast redirect to WhatsApp + Async pixel firing

**Performance Target:** <300ms total

**Flow:**
1. Find lead by fbclid (10ms)
2. Update lead with IP/UA (5ms)
3. Return redirect IMMEDIATELY (total: ~15ms)
4. Fire CAPI event ASYNC in background (doesn't block)

**URL:** `/r/abc123xyz`  
**Response:** 302 redirect to WhatsApp

**Background Tasks:**
- Send Lead event to Facebook CAPI
- Log for analytics
