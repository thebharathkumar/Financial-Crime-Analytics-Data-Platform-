// pages/api/risk-scores.js
export default function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const riskScores = [
    { entityId: 'ENT-401', entityName: 'Eastern European Exports GmbH', score: 95.7, riskLevel: 'CRITICAL', pepFlag: true, countryCode: 'RU', lastUpdated: '2026-03-25T07:00:00Z' },
    { entityId: 'ENT-245', entityName: 'Meridian Holdings Corp', score: 92.1, riskLevel: 'CRITICAL', pepFlag: false, countryCode: 'HK', lastUpdated: '2026-03-23T14:15:00Z' },
    { entityId: 'ENT-100', entityName: 'Global Trade Finance Ltd', score: 87.5, riskLevel: 'HIGH', pepFlag: false, countryCode: 'AE', lastUpdated: '2026-03-24T08:30:00Z' },
    { entityId: 'ENT-089', entityName: 'Offshore Investment Partners', score: 81.0, riskLevel: 'HIGH', pepFlag: true, countryCode: 'KY', lastUpdated: '2026-03-22T16:20:00Z' },
    { entityId: 'ENT-312', entityName: 'Pacific Rim Trading LLC', score: 74.3, riskLevel: 'HIGH', pepFlag: false, countryCode: 'CN', lastUpdated: '2026-03-23T09:45:00Z' },
    { entityId: 'ENT-156', entityName: 'Continental Asset Management', score: 69.8, riskLevel: 'MEDIUM', pepFlag: false, countryCode: 'DE', lastUpdated: '2026-03-21T11:00:00Z' },
    { entityId: 'ENT-210', entityName: 'Blue Ridge Capital LLC', score: 42.0, riskLevel: 'MEDIUM', pepFlag: false, countryCode: 'US', lastUpdated: '2026-03-20T10:00:00Z' },
    { entityId: 'ENT-055', entityName: 'Sunrise Import Export Co.', score: 18.5, riskLevel: 'LOW', pepFlag: false, countryCode: 'JP', lastUpdated: '2026-03-19T09:00:00Z' },
  ];

  const distribution = {
    CRITICAL: riskScores.filter(r => r.riskLevel === 'CRITICAL').length,
    HIGH: riskScores.filter(r => r.riskLevel === 'HIGH').length,
    MEDIUM: riskScores.filter(r => r.riskLevel === 'MEDIUM').length,
    LOW: riskScores.filter(r => r.riskLevel === 'LOW').length,
  };

  res.status(200).json({
    total: riskScores.length,
    distribution,
    riskScores,
    generatedAt: new Date().toISOString(),
  });
}
