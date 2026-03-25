// pages/api/stats.js
export default function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  res.status(200).json({
    overview: {
      totalAlerts: 156,
      openAlerts: 89,
      criticalEntities: 12,
      transactionsMonitored: 48320,
      totalValueFlagged: 24500000,
      avgRiskScore: 58.4,
      casesUnderReview: 23,
      sarsFiledMtd: 7,
    },
    alertTrend: [
      { date: '2026-03-19', count: 18 },
      { date: '2026-03-20', count: 22 },
      { date: '2026-03-21', count: 15 },
      { date: '2026-03-22', count: 31 },
      { date: '2026-03-23', count: 28 },
      { date: '2026-03-24', count: 19 },
      { date: '2026-03-25', count: 24 },
    ],
    alertsByType: {
      STRUCTURING: 45,
      LAYERING: 38,
      RAPID_MOVEMENT: 29,
      HIGH_VALUE: 22,
      ROUND_TRIP: 14,
      OTHER: 8,
    },
    generatedAt: new Date().toISOString(),
  });
}
