import React, { useEffect, useState } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
import { getBrandHealth, BrandHealthData } from '../../services/ownerDashboard';

function StarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

export default function BrandHealthPanel() {
  const [data, setData] = useState<BrandHealthData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const health = await getBrandHealth();
        setData(health);
      } catch (err) {
        console.error('Failed to fetch brand health', err);
      } finally {
        setLoading(false);
      }
    }
    fetchHealth();
  }, []);

  if (loading) {
    return (
      <div className="z3-new-panel">
        <div className="owner-dash-loading-row"><div className="spinner spinner-sm" /></div>
      </div>
    );
  }

  if (!data) return null;

  const getTrendClass = (trend: string) => {
    if (trend === 'up') return 'text-success';
    if (trend === 'down') return 'text-warning';
    return 'text-muted';
  };

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
          <span className="z3-rating-value">{data.overall_rating}<span className="z3-rating-star">★</span></span>
          <span className="z3-rating-sub">Based on {(data.total_reviews / 1000).toFixed(1)}k reviews</span>
        </div>
        <div className="z3-rating-card">
          <span className="z3-rating-platform">
            <span className="z3-platform-logo" style={{ background: '#FC8019' }}>S</span>
            Swiggy
          </span>
          <span className="z3-rating-value">{data.platforms.swiggy.rating}<span className="z3-rating-star">★</span></span>
          <span className={`z3-rating-sub ${getTrendClass(data.platforms.swiggy.trend)}`}>
            {data.platforms.swiggy.label}
          </span>
        </div>
        <div className="z3-rating-card">
          <span className="z3-rating-platform">
            <span className="z3-platform-logo" style={{ background: '#E23744' }}>Z</span>
            Zomato
          </span>
          <span className="z3-rating-value">{data.platforms.zomato.rating}<span className="z3-rating-star">★</span></span>
          <span className={`z3-rating-sub ${getTrendClass(data.platforms.zomato.trend)}`}>
            {data.platforms.zomato.label}
          </span>
        </div>
        <div className="z3-rating-card">
          <span className="z3-rating-platform">
            <span className="z3-platform-logo" style={{ background: '#4285F4' }}>G</span>
            Google
          </span>
          <span className="z3-rating-value">{data.platforms.google.rating}<span className="z3-rating-star">★</span></span>
          <span className={`z3-rating-sub ${getTrendClass(data.platforms.google.trend)}`}>
            {data.platforms.google.label}
          </span>
        </div>
      </div>

      <div className="z3-insight-box mt-4">
        <div className="z3-insight-header">
          <span className="z3-insight-icon">✨</span>
          <span className="z3-insight-title">AI Synthesis: Last 7 Days</span>
        </div>
        <div className="z3-insight-content">
          <p><strong>Highlights:</strong> {data.ai_synthesis.highlights}</p>
          <p className="mt-2"><strong>Areas for Improvement:</strong> {data.ai_synthesis.improvements}</p>
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
                  data={data.platform_distribution}
                  cx="50%"
                  cy="45%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {data.platform_distribution.map((entry, index) => (
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

          {/* Right: Retention Rates (Static for now as requested) */}
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
