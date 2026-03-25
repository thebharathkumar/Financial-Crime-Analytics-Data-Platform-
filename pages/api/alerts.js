// pages/api/alerts.js
export default function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const alerts = [
    {
      alertId: 'ALT-2026-001',
      entityId: 'ENT-100',
      entityName: 'Global Trade Finance Ltd',
      alertType: 'STRUCTURING',
      riskScore: 87.5,
      status: 'OPEN',
      createdAt: '2026-03-24T08:30:00Z',
      description: 'Multiple transactions just below $10,000 threshold detected within 7-day window',
      transactionCount: 8,
      totalAmount: 78450.00,
      currency: 'USD',
    },
    {
      alertId: 'ALT-2026-002',
      entityId: 'ENT-245',
      entityName: 'Meridian Holdings Corp',
      alertType: 'LAYERING',
      riskScore: 92.1,
      status: 'UNDER_REVIEW',
      createdAt: '2026-03-23T14:15:00Z',
      description: 'Complex layering pattern detected: 5-hop transaction chain across 4 jurisdictions',
      transactionCount: 12,
      totalAmount: 2340000.00,
      currency: 'USD',
    },
    {
      alertId: 'ALT-2026-003',
      entityId: 'ENT-312',
      entityName: 'Pacific Rim Trading LLC',
      alertType: 'RAPID_MOVEMENT',
      riskScore: 74.3,
      status: 'OPEN',
      createdAt: '2026-03-23T09:45:00Z',
      description: 'High-velocity fund movement: 63 transactions in 24 hours exceeding velocity threshold',
      transactionCount: 63,
      totalAmount: 1850000.00,
      currency: 'USD',
    },
    {
      alertId: 'ALT-2026-004',
      entityId: 'ENT-089',
      entityName: 'Offshore Investment Partners',
      alertType: 'HIGH_VALUE',
      riskScore: 81.0,
      status: 'ESCALATED',
      createdAt: '2026-03-22T16:20:00Z',
      description: 'Large single transaction ($4.2M) to high-risk jurisdiction with no prior transaction history',
      transactionCount: 1,
      totalAmount: 4200000.00,
      currency: 'USD',
    },
    {
      alertId: 'ALT-2026-005',
      entityId: 'ENT-156',
      entityName: 'Continental Asset Management',
      alertType: 'STRUCTURING',
      riskScore: 69.8,
      status: 'CLOSED',
      createdAt: '2026-03-21T11:00:00Z',
      description: 'Structuring pattern resolved — legitimate trade finance activity confirmed',
      transactionCount: 5,
      totalAmount: 45000.00,
      currency: 'USD',
    },
    {
      alertId: 'ALT-2026-006',
      entityId: 'ENT-401',
      entityName: 'Eastern European Exports GmbH',
      alertType: 'LAYERING',
      riskScore: 95.7,
      status: 'OPEN',
      createdAt: '2026-03-25T07:00:00Z',
      description: 'PEP-linked entity with round-trip transaction pattern detected via network analysis',
      transactionCount: 18,
      totalAmount: 6780000.00,
      currency: 'EUR',
    },
  ];

  // Apply optional filters
  const { status, alertType, minRisk } = req.query;
  let filtered = alerts;
  if (status) filtered = filtered.filter(a => a.status === status);
  if (alertType) filtered = filtered.filter(a => a.alertType === alertType);
  if (minRisk) filtered = filtered.filter(a => a.riskScore >= parseFloat(minRisk));

  res.status(200).json({
    total: filtered.length,
    alerts: filtered,
    generatedAt: new Date().toISOString(),
  });
}
