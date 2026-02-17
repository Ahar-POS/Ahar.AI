/**
 * ReportsPage component.
 *
 * Business reports with order summaries, charts, and analytics.
 */

import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from 'recharts';
import SubTabNavigation, { SubTab } from '../components/SubTabNavigation';
import './ReportsPage.css';

// Sub-tab definitions
const SUB_TABS: SubTab[] = [
  { id: 'summary', label: 'Order Summary' },
  { id: 'analytics', label: 'Analytics' },
];

// Mock data for KPI cards
const KPI_DATA = {
  ordersCompleted: 847,
  itemsSold: 2341,
  avgFulfillment: 14,
  topDish: { name: 'Pizza Margherita', count: 156 },
  topDrink: { name: 'House Wine', count: 234 },
  topWaiter: { name: 'Sofia Bianchi', orders: 87 },
  peakTime: { day: 'Saturday', time: '8 PM', orders: 47 },
};

// Mock data for top dishes chart
const TOP_DISHES_DATA = [
  { name: 'Pizza Margherita', count: 156 },
  { name: 'Spaghetti Carbonara', count: 142 },
  { name: 'Tiramisù', count: 98 },
  { name: 'Risotto Funghi', count: 89 },
  { name: 'Bruschetta', count: 76 },
];

// Mock data for top drinks chart
const TOP_DRINKS_DATA = [
  { name: 'House Wine', count: 234 },
  { name: 'Espresso', count: 187 },
  { name: 'Cappuccino', count: 156 },
  { name: 'Limoncello', count: 67 },
];

// Mock data for hourly distribution
const HOURLY_DATA = [
  { hour: '11:00', antipasti: 5, primiPiatti: 12, pizze: 8, dolci: 3 },
  { hour: '12:00', antipasti: 15, primiPiatti: 22, pizze: 18, dolci: 8 },
  { hour: '13:00', antipasti: 25, primiPiatti: 28, pizze: 22, dolci: 12 },
  { hour: '14:00', antipasti: 18, primiPiatti: 15, pizze: 12, dolci: 10 },
  { hour: '18:00', antipasti: 12, primiPiatti: 18, pizze: 15, dolci: 8 },
  { hour: '19:00', antipasti: 22, primiPiatti: 25, pizze: 28, dolci: 15 },
  { hour: '20:00', antipasti: 28, primiPiatti: 32, pizze: 38, dolci: 22 },
  { hour: '21:00', antipasti: 20, primiPiatti: 22, pizze: 25, dolci: 18 },
  { hour: '22:00', antipasti: 8, primiPiatti: 12, pizze: 15, dolci: 8 },
];

// Mock data for biggest days
const BIGGEST_DAYS_DATA = [
  { rank: 1, date: 'Dec 14, 2024', orders: 47 },
  { rank: 2, date: 'Dec 7, 2024', orders: 43 },
  { rank: 3, date: 'Nov 30, 2024', orders: 41 },
  { rank: 4, date: 'Nov 23, 2024', orders: 38 },
  { rank: 5, date: 'Dec 1, 2024', orders: 35 },
];

/**
 * Reports page component.
 */
export default function ReportsPage() {
  const [activeSubTab, setActiveSubTab] = useState('summary');

  return (
    <div className="reports-page">
      {/* Header */}
      <div className="reports-page-header">
        <h1 className="reports-page-title">Business Reports</h1>
      </div>

      {/* Sub-tabs */}
      <div className="reports-page-tabs">
        <SubTabNavigation
          tabs={SUB_TABS}
          activeTabId={activeSubTab}
          onTabChange={setActiveSubTab}
        />
      </div>

      {/* Content */}
      <div className="reports-page-content">
        {activeSubTab === 'summary' ? (
          <OrderSummaryView />
        ) : (
          <AnalyticsView />
        )}
      </div>
    </div>
  );
}

/**
 * Order Summary view with KPIs and biggest days.
 */
function OrderSummaryView() {
  return (
    <div className="reports-summary">
      {/* KPI Grid */}
      <div className="reports-kpi-grid">
        {/* Orders Completed */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-card-label">Orders Completed</span>
            <span className="kpi-card-icon kpi-icon-orders">📋</span>
          </div>
          <div className="kpi-card-value">{KPI_DATA.ordersCompleted.toLocaleString()}</div>
          <div className="kpi-card-subtext">{KPI_DATA.itemsSold.toLocaleString()} items sold</div>
        </div>

        {/* Avg Fulfillment */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-card-label">Avg Fulfillment</span>
            <span className="kpi-card-icon kpi-icon-time">⏱️</span>
          </div>
          <div className="kpi-card-value">{KPI_DATA.avgFulfillment} min</div>
          <div className="kpi-card-subtext">Per order</div>
        </div>

        {/* Top Dish */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-card-label">Top Dish</span>
            <span className="kpi-card-icon kpi-icon-dish">🍝</span>
          </div>
          <div className="kpi-card-value kpi-value-text">{KPI_DATA.topDish.name}</div>
          <div className="kpi-card-subtext">{KPI_DATA.topDish.count} sold</div>
        </div>

        {/* Top Drink */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-card-label">Top Drink</span>
            <span className="kpi-card-icon kpi-icon-drink">🍷</span>
          </div>
          <div className="kpi-card-value kpi-value-text">{KPI_DATA.topDrink.name}</div>
          <div className="kpi-card-subtext">{KPI_DATA.topDrink.count} sold</div>
        </div>

        {/* Top Waiter */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-card-label">Top Waiter</span>
            <span className="kpi-card-icon kpi-icon-staff">👤</span>
          </div>
          <div className="kpi-card-value kpi-value-text">{KPI_DATA.topWaiter.name}</div>
          <div className="kpi-card-subtext">{KPI_DATA.topWaiter.orders} orders</div>
        </div>

        {/* Peak Time */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-card-label">Peak Time</span>
            <span className="kpi-card-icon kpi-icon-peak">📈</span>
          </div>
          <div className="kpi-card-value kpi-value-text">{KPI_DATA.peakTime.day}</div>
          <div className="kpi-card-subtext">
            {KPI_DATA.peakTime.time} – {KPI_DATA.peakTime.orders} orders
          </div>
        </div>
      </div>

      {/* Biggest Days */}
      <div className="reports-biggest-days">
        <h3 className="section-title">
          <span className="section-icon">📈</span>
          Biggest Days (Top 5)
        </h3>
        <div className="biggest-days-list">
          {BIGGEST_DAYS_DATA.map((day) => (
            <div key={day.rank} className="biggest-day-item">
              <span className={`biggest-day-rank rank-${day.rank}`}>{day.rank}</span>
              <span className="biggest-day-date">{day.date}</span>
              <div className="biggest-day-orders">
                <span className="biggest-day-count">{day.orders}</span>
                <span className="biggest-day-label">orders</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Analytics view with charts.
 */
function AnalyticsView() {
  return (
    <div className="reports-analytics">
      {/* Top Performing Dishes */}
      <div className="chart-card">
        <h3 className="chart-title">
          <span className="chart-icon">🍝</span>
          Top Performing Dishes
        </h3>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={TOP_DISHES_DATA} layout="horizontal">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="name"
                tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
                angle={-35}
                textAnchor="end"
                height={80}
              />
              <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'var(--color-text-primary)' }}
              />
              <Bar dataKey="count" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Performing Drinks */}
      <div className="chart-card">
        <h3 className="chart-title">
          <span className="chart-icon">🍷</span>
          Top Performing Drinks
        </h3>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={TOP_DRINKS_DATA} layout="horizontal">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="name"
                tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
                angle={-35}
                textAnchor="end"
                height={80}
              />
              <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'var(--color-text-primary)' }}
              />
              <Bar dataKey="count" fill="#dc2626" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Order Distribution by Hour */}
      <div className="chart-card chart-card-wide">
        <h3 className="chart-title">Order Distribution by Hour</h3>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={HOURLY_DATA}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="hour"
                tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
              />
              <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'var(--color-text-primary)' }}
              />
              <Legend
                wrapperStyle={{ paddingTop: '20px' }}
                formatter={(value) => (
                  <span style={{ color: 'var(--color-text-secondary)' }}>{value}</span>
                )}
              />
              <Line
                type="monotone"
                dataKey="antipasti"
                name="Antipasti"
                stroke="#dc2626"
                strokeWidth={2}
                dot={{ fill: '#dc2626', strokeWidth: 2 }}
              />
              <Line
                type="monotone"
                dataKey="primiPiatti"
                name="Primi Piatti"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={{ fill: '#f59e0b', strokeWidth: 2 }}
              />
              <Line
                type="monotone"
                dataKey="pizze"
                name="Pizze"
                stroke="#22c55e"
                strokeWidth={2}
                dot={{ fill: '#22c55e', strokeWidth: 2 }}
              />
              <Line
                type="monotone"
                dataKey="dolci"
                name="Dolci"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={{ fill: '#8b5cf6', strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
