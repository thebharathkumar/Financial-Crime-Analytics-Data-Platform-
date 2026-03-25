// pages/api/transactions.js
export default function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const transactions = [
    { transactionId: 'TXN-001', sourceAccount: 'ACC-1001', destinationAccount: 'ACC-2001', amount: 9800.00, currency: 'USD', transactionType: 'WIRE', status: 'COMPLETED', timestamp: '2026-03-25T08:00:00Z', riskScore: 78.5, flagged: true },
    { transactionId: 'TXN-002', sourceAccount: 'ACC-1001', destinationAccount: 'ACC-2002', amount: 9750.00, currency: 'USD', transactionType: 'WIRE', status: 'COMPLETED', timestamp: '2026-03-25T09:30:00Z', riskScore: 80.1, flagged: true },
    { transactionId: 'TXN-003', sourceAccount: 'ACC-2001', destinationAccount: 'ACC-3001', amount: 2340000.00, currency: 'USD', transactionType: 'SWIFT', status: 'COMPLETED', timestamp: '2026-03-24T14:00:00Z', riskScore: 92.1, flagged: true },
    { transactionId: 'TXN-004', sourceAccount: 'ACC-3001', destinationAccount: 'ACC-4001', amount: 1200000.00, currency: 'EUR', transactionType: 'SWIFT', status: 'COMPLETED', timestamp: '2026-03-24T15:30:00Z', riskScore: 88.4, flagged: true },
    { transactionId: 'TXN-005', sourceAccount: 'ACC-5001', destinationAccount: 'ACC-6001', amount: 1500.00, currency: 'USD', transactionType: 'ACH', status: 'COMPLETED', timestamp: '2026-03-25T10:00:00Z', riskScore: 12.3, flagged: false },
    { transactionId: 'TXN-006', sourceAccount: 'ACC-7001', destinationAccount: 'ACC-8001', amount: 45000.00, currency: 'GBP', transactionType: 'WIRE', status: 'PENDING', timestamp: '2026-03-25T11:00:00Z', riskScore: 55.0, flagged: false },
    { transactionId: 'TXN-007', sourceAccount: 'ACC-9001', destinationAccount: 'ACC-1001', amount: 4200000.00, currency: 'USD', transactionType: 'SWIFT', status: 'COMPLETED', timestamp: '2026-03-22T16:00:00Z', riskScore: 95.7, flagged: true },
    { transactionId: 'TXN-008', sourceAccount: 'ACC-1002', destinationAccount: 'ACC-2003', amount: 3200.00, currency: 'USD', transactionType: 'ACH', status: 'COMPLETED', timestamp: '2026-03-25T07:30:00Z', riskScore: 8.2, flagged: false },
  ];

  const { flagged, minAmount } = req.query;
  let filtered = transactions;
  if (flagged === 'true') filtered = filtered.filter(t => t.flagged);
  if (minAmount) filtered = filtered.filter(t => t.amount >= parseFloat(minAmount));

  res.status(200).json({
    total: filtered.length,
    transactions: filtered,
    generatedAt: new Date().toISOString(),
  });
}
