import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

const platformData = [
  { name: 'Dine-in', value: 45, color: '#000000' },    // Uber Black
  { name: 'Takeaway', value: 15, color: '#00A86B' },   // Uber Green
  { name: 'Swiggy', value: 25, color: '#FC8019' },     // Swiggy Orange
  { name: 'Zomato', value: 15, color: '#E23744' },     // Zomato Red
];

function StarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

export default function BrandHealthPanel() {
  return (
    <div className="z3-new-panel">
      <h3 className="z3-panel-section-title">
        <StarIcon /> Brand Health & Experience
      </h3>

      <div className="z3-ratings-row">
        <div className="z3-rating-card">
          <span className="z3-rating-platform">
            Overall
          </span>
          <span className="z3-rating-value">4.6<span className="z3-rating-star">★</span></span>
          <span className="z3-rating-sub">Based on 1.2k reviews</span>
        </div>
        <div className="z3-rating-card">
          <span className="z3-rating-platform">
            <span className="z3-platform-logo" style={{ background: '#FC8019' }}>S</span>
            Swiggy
          </span>
          <span className="z3-rating-value">4.2<span className="z3-rating-star">★</span></span>
          <span className="z3-rating-sub text-warning">↓ 0.2 this week</span>
        </div>
        <div className="z3-rating-card">
          <span className="z3-rating-platform">
            <span className="z3-platform-logo" style={{ background: '#E23744' }}>Z</span>
            Zomato
          </span>
          <span className="z3-rating-value">4.5<span className="z3-rating-star">★</span></span>
          <span className="z3-rating-sub text-success">Stable</span>
        </div>
        <div className="z3-rating-card">
          <span className="z3-rating-platform">
            <span className="z3-platform-logo" style={{ background: '#4285F4' }}>G</span>
            Google
          </span>
          <span className="z3-rating-value">4.8<span className="z3-rating-star">★</span></span>
          <span className="z3-rating-sub text-success">High visibility</span>
        </div>
      </div>

      <div className="z3-insight-box mt-4">
        <div className="z3-insight-header">
          <span className="z3-insight-icon">✨</span>
          <span className="z3-insight-title">AI Synthesis: Last 7 Days</span>
        </div>
        <div className="z3-insight-content">
          <p><strong>Highlights:</strong> Strong positive sentiment around the new Truffle Pasta addition. Staff member 'Priya' mentioned favorably in 4 Google reviews for excellent service.</p>
          <p className="mt-2"><strong>Areas for Improvement:</strong> Detected a spike in complaints regarding <em>"cold food"</em> on Swiggy deliveries specifically between 7:30 PM and 8:30 PM. Suggest investigating dispatcher availability during this peak hour.</p>
        </div>
      </div>

      <div className="z3-chart-container mt-4" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <h4 className="z3-chart-title">Platform Volume & Retention</h4>
        <p className="z3-chart-subtitle">Distribution of today's orders and channel retention</p>
        
        <div style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', marginTop: '16px', gap: '24px', flex: 1 }}>
          {/* Left: Donut Chart */}
          <div style={{ width: '50%', height: '220px', display: 'flex', flexDirection: 'column' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={platformData}
                  cx="50%"
                  cy="45%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {platformData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value: number) => [`${value}%`, 'Share']}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                />
                <Legend verticalAlign="bottom" height={36} iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Right: Retention Rates */}
          <div style={{ width: '50%', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '16px' }}>
            <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
              Customer Retention
            </h5>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
              <span style={{ fontSize: '14px', fontWeight: 600 }}>Dine-in</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '20px', fontWeight: 800 }}>68%</span>
                <span style={{ fontSize: '12px', color: '#10B981', fontWeight: 600 }}>↑ 5%</span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
              <span style={{ fontSize: '14px', fontWeight: 600 }}>Swiggy</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '20px', fontWeight: 800 }}>32%</span>
                <span style={{ fontSize: '12px', color: '#EF4444', fontWeight: 600 }}>↓ 2%</span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '8px' }}>
              <span style={{ fontSize: '14px', fontWeight: 600 }}>Zomato</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '20px', fontWeight: 800 }}>35%</span>
                <span style={{ fontSize: '12px', color: '#10B981', fontWeight: 600 }}>↑ 1%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
