import { useState, useMemo } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend
} from 'recharts';

// Mock data generator for 12 hours of the day
const times = ['11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00'];

const availableDishes = [
    { id: 'pizza', name: 'Pizza Margherita', color: '#ef4444', total: 487, trend: '+12%' },
    { id: 'carbonara', name: 'Spaghetti Carbonara', color: '#f59e0b', total: 412, trend: '+8%' },
    { id: 'tiramisu', name: 'Tiramisù', color: '#10b981', total: 298, trend: '+22%' },
    { id: 'risotto', name: 'Risotto Funghi', color: '#6366f1', total: 276, trend: '+18%' },
    { id: 'bruschetta', name: 'Bruschetta', color: '#8b5cf6', total: 234, trend: '+5%' },
    { id: 'lasagna', name: 'Lasagna al Forno', color: '#ec4899', total: 198, trend: '-3%' },
    { id: 'caprese', name: 'Insalata Caprese', color: '#14b8a6', total: 167, trend: '+2%' },
];

const generateData = () => {
    return times.map(time => {
        const dataPoint: any = { time };
        availableDishes.forEach(dish => {
            // Create interesting bell curves centered around peak hours
            const isPeak = time === '13:00' || time === '20:00';
            const base = isPeak ? 30 : 10;
            dataPoint[dish.id] = Math.floor(base + Math.random() * 15 - 5) * (dish.total / 500);
        });
        return dataPoint;
    });
};

const chartData = generateData();

export default function CatalogueTab() {
    const [selectedDishes, setSelectedDishes] = useState<string[]>([]);

    const handleDishToggle = (dishId: string) => {
        setSelectedDishes(prev => {
            if (prev.includes(dishId)) {
                return prev.filter(id => id !== dishId);
            }
            if (prev.length >= 5) {
                // Can optionally show a toast warning here
                return prev;
            }
            return [...prev, dishId];
        });
    };

    const selectedDishObjects = useMemo(() =>
        availableDishes.filter(d => selectedDishes.includes(d.id)),
        [selectedDishes]);

    return (
        <div className="tab-container">
            {/* Chart Section */}
            <div className="chart-section">
                <div className="chart-header">
                    <div>
                        <h4 className="chart-title">Order Distribution Timeline</h4>
                        <p className="chart-subtitle">Track how each dish sells over time. Click dishes below to compare.</p>
                    </div>
                </div>
                <div className="chart-container">
                    {selectedDishes.length > 0 ? (
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 10 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} dy={10} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}
                                    itemStyle={{ fontSize: '13px', fontWeight: 600 }}
                                    labelStyle={{ fontSize: '13px', color: '#6b7280', marginBottom: '8px' }}
                                />
                                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '20px' }} />
                                {selectedDishObjects.map(dish => (
                                    <Line
                                        key={dish.id}
                                        type="monotone"
                                        dataKey={dish.id}
                                        name={dish.name}
                                        stroke={dish.color}
                                        strokeWidth={3}
                                        dot={{ r: 4, strokeWidth: 2 }}
                                        activeDot={{ r: 6, strokeWidth: 0 }}
                                    />
                                ))}
                            </LineChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="empty-chart-state">
                            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 3v18h18" />
                                <path d="m19 9-5 5-4-4-3 3" />
                            </svg>
                            <p>Select up to 5 dishes below to compare their sales timelines</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Selector Section */}
            <div className="selector-section">
                <h5 className="selector-title">SELECT DISHES TO COMPARE (MAX 5)</h5>
                <div className="dish-cards-grid">
                    {availableDishes.map(dish => {
                        const isSelected = selectedDishes.includes(dish.id);
                        const isMaxedOut = selectedDishes.length >= 5 && !isSelected;
                        return (
                            <button
                                key={dish.id}
                                className={`dish-card ${isSelected ? 'selected' : ''}`}
                                onClick={() => handleDishToggle(dish.id)}
                                disabled={isMaxedOut}
                                aria-pressed={isSelected}
                            >
                                <div className="dish-card-header">
                                    <span className="dish-name">{dish.name}</span>
                                    {isSelected && (
                                        <span className="dish-color-indicator" style={{ backgroundColor: dish.color }}></span>
                                    )}
                                </div>
                                <div className="dish-card-stats">
                                    <span className="dish-total">{dish.total}</span>
                                    <span className={`dish-trend ${dish.trend.startsWith('+') ? 'text-success' : 'text-error'}`}>
                                        {dish.trend}
                                    </span>
                                </div>
                                <div className="dish-card-footer">
                                    <span className="footer-label">total orders</span>
                                    <span className="footer-label">trend</span>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
