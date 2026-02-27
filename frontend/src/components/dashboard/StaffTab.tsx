
const attendanceData = {
    present: [
        { name: 'Sofia Bianchi', role: 'Server', time: '08:00 AM' },
        { name: 'Marco Rossi', role: 'Head Chef', time: '07:30 AM' },
        { name: 'Giulia Colombo', role: 'Bartender', time: '09:00 AM' }
    ],
    absent: [
        { name: 'Luca Ricci', role: 'Server', reason: 'Sick Leave' }
    ]
};

export default function StaffTab() {
    return (
        <div className="tab-container scrollable-tab">

            <div className="charts-grid mt-4">
                <div className="chart-card" style={{ padding: '0', background: 'transparent', border: 'none', boxShadow: 'none' }}>
                    <div className="metrics-2x2-grid">

                        {/* Metric 1 */}
                        <div className="metric-card">
                            <div className="metric-header">
                                <span className="metric-label">Labor Cost / Rev</span>
                                <span className="metric-icon">💵</span>
                            </div>
                            <div className="metric-value">22.4%</div>
                            <div className="metric-subtext text-success">↓ -1.2% below target</div>
                        </div>

                        {/* Metric 2 */}
                        <div className="metric-card">
                            <div className="metric-header">
                                <span className="metric-label">Shifts Filled</span>
                                <span className="metric-icon">👥</span>
                            </div>
                            <div className="metric-value">92%</div>
                            <div className="metric-subtext text-warning">↑ 5% vs last week</div>
                        </div>

                        {/* Metric 3 */}
                        <div className="metric-card">
                            <div className="metric-header">
                                <span className="metric-label">Avg Table Turnover</span>
                                <span className="metric-icon">⏱️</span>
                            </div>
                            <div className="metric-value">45 mins</div>
                            <div className="metric-subtext text-success">Optimal pacing</div>
                        </div>

                        {/* Metric 4 */}
                        <div className="metric-card">
                            <div className="metric-header">
                                <span className="metric-label">Total Daily Guests</span>
                                <span className="metric-icon">🍽️</span>
                            </div>
                            <div className="metric-value">2117</div>
                            <div className="metric-subtext">Matches 847 orders (+15% vol)</div>
                        </div>

                    </div>
                </div>

                <div className="chart-card">
                    <h4 className="chart-title mb-2">Live Staff Status</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                        <div>
                            <h5 style={{ fontSize: '12px', fontWeight: 600, color: '#10b981', marginBottom: '8px', textTransform: 'uppercase' }}>Present ({attendanceData.present.length})</h5>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {attendanceData.present.map((staff, i) => (
                                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: '#f9fafb', borderRadius: '6px', border: '1px solid #f3f4f6' }}>
                                        <div>
                                            <div style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>{staff.name}</div>
                                            <div style={{ fontSize: '11px', color: '#6b7280' }}>{staff.role}</div>
                                        </div>
                                        <div style={{ fontSize: '12px', color: '#10b981', fontWeight: 500 }}>In since {staff.time}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div>
                            <h5 style={{ fontSize: '12px', fontWeight: 600, color: '#ef4444', marginBottom: '8px', textTransform: 'uppercase' }}>Absent ({attendanceData.absent.length})</h5>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {attendanceData.absent.map((staff, i) => (
                                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: '#fef2f2', borderRadius: '6px', border: '1px solid #fee2e2' }}>
                                        <div>
                                            <div style={{ fontSize: '13px', fontWeight: 600, color: '#991b1b' }}>{staff.name}</div>
                                            <div style={{ fontSize: '11px', color: '#b91c1c' }}>{staff.role}</div>
                                        </div>
                                        <div style={{ fontSize: '12px', color: '#ef4444', fontWeight: 500 }}>{staff.reason}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
