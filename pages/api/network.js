// pages/api/network.js
export default function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Network graph data for visualization
  const nodes = [
    { id: 'ENT-401', label: 'Eastern European\nExports GmbH', type: 'ENTITY', riskLevel: 'CRITICAL', x: 300, y: 200 },
    { id: 'ENT-245', label: 'Meridian Holdings\nCorp', type: 'ENTITY', riskLevel: 'CRITICAL', x: 600, y: 100 },
    { id: 'ACC-9001', label: 'ACC-9001', type: 'ACCOUNT', riskLevel: 'HIGH', x: 200, y: 350 },
    { id: 'ACC-1001', label: 'ACC-1001', type: 'ACCOUNT', riskLevel: 'HIGH', x: 450, y: 350 },
    { id: 'ACC-2001', label: 'ACC-2001', type: 'ACCOUNT', riskLevel: 'HIGH', x: 650, y: 300 },
    { id: 'ACC-3001', label: 'ACC-3001', type: 'ACCOUNT', riskLevel: 'HIGH', x: 800, y: 200 },
    { id: 'ENT-312', label: 'Pacific Rim\nTrading LLC', type: 'ENTITY', riskLevel: 'HIGH', x: 150, y: 150 },
    { id: 'ACC-4001', label: 'ACC-4001', type: 'ACCOUNT', riskLevel: 'MEDIUM', x: 900, y: 350 },
  ];

  const edges = [
    { source: 'ENT-401', target: 'ACC-9001', amount: 4200000, currency: 'USD', label: '$4.2M' },
    { source: 'ACC-9001', target: 'ACC-1001', amount: 4200000, currency: 'USD', label: '$4.2M' },
    { source: 'ACC-1001', target: 'ACC-2001', amount: 2340000, currency: 'USD', label: '$2.34M' },
    { source: 'ACC-2001', target: 'ACC-3001', amount: 2340000, currency: 'USD', label: '$2.34M' },
    { source: 'ACC-3001', target: 'ACC-4001', amount: 1200000, currency: 'EUR', label: '€1.2M' },
    { source: 'ENT-245', target: 'ACC-2001', amount: 500000, currency: 'USD', label: '$500K' },
    { source: 'ENT-312', target: 'ACC-1001', amount: 980000, currency: 'USD', label: '$980K' },
  ];

  res.status(200).json({ nodes, edges, generatedAt: new Date().toISOString() });
}
