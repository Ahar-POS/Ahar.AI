import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

const hourlyFlowData = [
  { time: '11:00', fulfillmentMin: 12 },
  { time: '12:00', fulfillmentMin: 15 },
  { time: '13:00', fulfillmentMin: 22 }, // Peak lunch rush delay
  { time: '14:00', fulfillmentMin: 18 },
  { time: '18:00', fulfillmentMin: 14 },
  { time: '19:00', fulfillmentMin: 25 },
  { time: '20:00', fulfillmentMin: 32 }, // Peak dinner rush delay
  { time: '21:00', fulfillmentMin: 19 },
];

const attendanceData = {
  present: [
    { name: 'Priya Sharma', role: 'Server', time: '08:00 AM' },
    { name: 'Rahul Verma', role: 'Head Chef', time: '07:30 AM' },
    { name: 'Anjali Desai', role: 'Bartender', time: '09:00 AM' }
  ],
  absent: [
    { name: 'Amit Patel', role: 'Server', reason: 'Sick Leave' }
  ]
};

function KitchenIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
      <path d="M7 2v20" />
      <path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
    </svg>
  );
}

export default function LiveOperationsPanel() {
  return (
    <div className="z3-new-panel">
      <h3 className="z3-panel-section-title">
        <KitchenIcon /> Kitchen & Staff Status
      </h3>

      <div className="z3-metrics-row">
        <div className="z3-metric-card">
          <span className="z3-metric-label">Avg Table Turnaround</span>
          <span className="z3-metric-value">45<span style={{fontSize: '24px', marginLeft: '4px'}}>m</span></span>
          <span className="z3-metric-sub text-success">Optimal</span>
        </div>
        <div className="z3-metric-card">
          <span className="z3-metric-label">Customer Wait (Dine-in)</span>
          <span className="z3-metric-value">14<span style={{fontSize: '24px', marginLeft: '4px'}}>m</span></span>
          <span className="z3-metric-sub text-warning">↑ 2m vs avg</span>
        </div>
        <div className="z3-metric-card">
          <span className="z3-metric-label">Delivery Partner Wait</span>
          <span className="z3-metric-value">6<span style={{fontSize: '24px', marginLeft: '4px'}}>m</span></span>
          <span className="z3-metric-sub text-success">Target met</span>
        </div>
      </div>

      <div className="z3-chart-container mt-4" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <h4 className="z3-chart-title">Average Fulfillment Time (mins) by Hour</h4>
        <div style={{ flex: 1, minHeight: '220px', width: '100%', marginTop: '4px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={hourlyFlowData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} dy={10} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
              <Tooltip 
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                formatter={(value: number) => [`${value} mins`, 'Fulfillment Time']}
              />
              <Line type="monotone" dataKey="fulfillmentMin" stroke="#000000" strokeWidth={3} dot={{ r: 4, fill: '#000' }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="z3-staff-split mt-4">
        <div className="z3-staff-section">
          <h4 className="z3-staff-title text-success">Present ({attendanceData.present.length})</h4>
          <div className="z3-staff-list">
            {attendanceData.present.map((staff, i) => (
              <div key={i} className="z3-staff-item z3-staff-item--present">
                <div>
                  <div className="z3-staff-name">{staff.name}</div>
                  <div className="z3-staff-role">{staff.role}</div>
                </div>
                <div className="z3-staff-time">In since {staff.time}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="z3-staff-section">
          <h4 className="z3-staff-title text-danger">Absent ({attendanceData.absent.length})</h4>
          <div className="z3-staff-list">
            {attendanceData.absent.map((staff, i) => (
              <div key={i} className="z3-staff-item z3-staff-item--absent">
                <div>
                  <div className="z3-staff-name text-danger">{staff.name}</div>
                  <div className="z3-staff-role">{staff.role}</div>
                </div>
                <div className="z3-staff-reason">{staff.reason}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
