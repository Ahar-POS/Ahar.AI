/**
 * AnalyticsPage component.
 *
 * Advanced analytics with demand patterns and prep recommendations.
 */

import React, { useState, useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import SubTabNavigation, { SubTab } from '../components/SubTabNavigation';
import './AnalyticsPage.css';

// Sub-tab definitions
const SUB_TABS: SubTab[] = [
  { id: 'timeline', label: 'Order Timeline' },
  { id: 'insights', label: 'AI Insights' },
  { id: 'prep', label: 'Prep Summary' },
];

// Date range options
const DATE_RANGES = [
  { id: 'last7', label: 'Last 7 Days' },
  { id: 'last30', label: 'Last 30 Days' },
  { id: 'last90', label: 'Last 90 Days' },
];

// Time of day options
const TIME_OPTIONS = [
  { id: 'all', label: 'All Day' },
  { id: 'lunch', label: 'Lunch (11-3)' },
  { id: 'dinner', label: 'Dinner (5-10)' },
];

// Day options
const DAY_OPTIONS = [
  { id: 'all', label: 'All Days' },
  { id: 'weekday', label: 'Weekdays' },
  { id: 'weekend', label: 'Weekends' },
];

// Generate timeline data for last 30 days
const generateTimelineData = () => {
  const data = [];
  const baseDate = new Date('2026-01-06');

  for (let i = 0; i < 30; i++) {
    const date = new Date(baseDate);
    date.setDate(date.getDate() + i);
    const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    data.push({
      date: dateStr,
      pizzaMargherita: Math.floor(12 + Math.random() * 16),
      spaghettiCarbonara: Math.floor(10 + Math.random() * 14),
      tiramisu: Math.floor(8 + Math.random() * 12),
      risottoFunghi: Math.floor(6 + Math.random() * 10),
      bruschetta: Math.floor(5 + Math.random() * 10),
    });
  }

  return data;
};

const TIMELINE_DATA = generateTimelineData();

// Dish data for comparison grid
const DISH_DATA = [
  {
    id: '1',
    name: 'Pizza Margherita',
    category: 'Pizze',
    totalOrders: 487,
    trend: 12,
    selected: true,
    color: '#dc2626',
  },
  {
    id: '2',
    name: 'Spaghetti Carbonara',
    category: 'Primi Piatti',
    totalOrders: 412,
    trend: 8,
    selected: true,
    color: '#f59e0b',
  },
  {
    id: '3',
    name: 'Tiramisù',
    category: 'Dolci',
    totalOrders: 298,
    trend: 22,
    selected: true,
    color: '#8b5cf6',
  },
  {
    id: '4',
    name: 'Risotto Funghi',
    category: 'Primi Piatti',
    totalOrders: 276,
    trend: 18,
    selected: true,
    color: '#22c55e',
  },
  {
    id: '5',
    name: 'Bruschetta',
    category: 'Antipasti',
    totalOrders: 234,
    trend: 5,
    selected: true,
    color: '#06b6d4',
  },
  {
    id: '6',
    name: 'Lasagna al Forno',
    category: 'Primi Piatti',
    totalOrders: 198,
    trend: -3,
    selected: false,
    color: '#ec4899',
  },
  {
    id: '7',
    name: 'Insalata Caprese',
    category: 'Antipasti',
    totalOrders: 167,
    trend: 2,
    selected: false,
    color: '#14b8a6',
  },
  {
    id: '8',
    name: 'Panna Cotta',
    category: 'Dolci',
    totalOrders: 145,
    trend: 15,
    selected: false,
    color: '#f97316',
  },
  {
    id: '9',
    name: 'Gnocchi Sorrentina',
    category: 'Primi Piatti',
    totalOrders: 45,
    trend: -8,
    selected: false,
    color: '#6366f1',
  },
  {
    id: '10',
    name: 'Vitello Tonnato',
    category: 'Secondi',
    totalOrders: 25,
    trend: 6,
    selected: false,
    color: '#84cc16',
  },
];

// Period summary stats
const PERIOD_SUMMARY = {
  totalItemsSold: 2287,
  uniqueItems: 10,
  avgOrdersPerDay: 8,
  itemsTrendingUp: 8,
};

// AI Insights data
const AI_INSIGHTS = [
  {
    type: 'opportunity',
    title: 'High Demand Pattern Detected',
    description:
      'Pizza Margherita orders spike 40% on Friday evenings between 7-9 PM. Consider pre-prepping extra dough.',
    impact: 'Could reduce wait times by 15%',
  },
  {
    type: 'warning',
    title: 'Inventory Alert',
    description:
      'Mozzarella usage is trending 25% higher than usual. Current stock may run low by Saturday.',
    impact: 'Order recommended: 5kg additional',
  },
  {
    type: 'suggestion',
    title: 'Menu Optimization',
    description:
      'Tiramisù has 22% growth but limited visibility. Consider featuring it in the "Chef Recommends" section.',
    impact: 'Estimated +30 orders/week',
  },
  {
    type: 'trend',
    title: 'Seasonal Trend',
    description:
      'Warm dishes (Risotto, Lasagna) are seeing increased orders as temperatures drop.',
    impact: 'Prep volumes should increase 15%',
  },
];

// Prep summary data
const PREP_SUMMARY = [
  { item: 'Pizza Dough', dailyNeeded: 45, unit: 'balls', prepTime: '4h ahead' },
  { item: 'Fresh Pasta', dailyNeeded: 8, unit: 'kg', prepTime: '2h ahead' },
  { item: 'Marinara Sauce', dailyNeeded: 12, unit: 'liters', prepTime: 'Morning' },
  { item: 'Tiramisù', dailyNeeded: 24, unit: 'portions', prepTime: 'Day before' },
  { item: 'Risotto Base', dailyNeeded: 6, unit: 'kg', prepTime: '1h ahead' },
  { item: 'Bruschetta Topping', dailyNeeded: 3, unit: 'kg', prepTime: '30m ahead' },
];

/**
 * Analytics page component.
 */
export default function AnalyticsPage() {
  const [activeSubTab, setActiveSubTab] = useState('timeline');
  const [dateRange, setDateRange] = useState('last30');
  const [timeOfDay, setTimeOfDay] = useState('all');
  const [dayFilter, setDayFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'daily' | 'weekly'>('daily');
  const [selectedDishes, setSelectedDishes] = useState<Set<string>>(
    new Set(DISH_DATA.filter((d) => d.selected).map((d) => d.id))
  );

  const handleDishToggle = (dishId: string) => {
    setSelectedDishes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(dishId)) {
        newSet.delete(dishId);
      } else if (newSet.size < 5) {
        newSet.add(dishId);
      }
      return newSet;
    });
  };

  const selectedDishData = useMemo(
    () => DISH_DATA.filter((d) => selectedDishes.has(d.id)),
    [selectedDishes]
  );

  return (
    <div className="analytics-page">
      {/* Header */}
      <div className="analytics-page-header">
        <div>
          <h1 className="analytics-page-title">
            <span className="title-icon">📊</span>
            Advanced Analytics
          </h1>
          <p className="analytics-page-subtitle">
            Deep insights into demand patterns and prep recommendations
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="analytics-filters">
        <div className="filter-group">
          <label className="filter-label">📅</label>
          <select
            className="filter-select"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
          >
            {DATE_RANGES.map((range) => (
              <option key={range.id} value={range.id}>
                {range.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label">🕐</label>
          <select
            className="filter-select"
            value={timeOfDay}
            onChange={(e) => setTimeOfDay(e.target.value)}
          >
            {TIME_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label">📆</label>
          <select
            className="filter-select"
            value={dayFilter}
            onChange={(e) => setDayFilter(e.target.value)}
          >
            {DAY_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="analytics-page-tabs">
        <SubTabNavigation
          tabs={SUB_TABS}
          activeTabId={activeSubTab}
          onTabChange={setActiveSubTab}
        />
      </div>

      {/* Content */}
      <div className="analytics-page-content">
        {activeSubTab === 'timeline' && (
          <TimelineView
            viewMode={viewMode}
            setViewMode={setViewMode}
            selectedDishes={selectedDishData}
            allDishes={DISH_DATA}
            onDishToggle={handleDishToggle}
            selectedIds={selectedDishes}
          />
        )}
        {activeSubTab === 'insights' && <InsightsView />}
        {activeSubTab === 'prep' && <PrepSummaryView />}
      </div>
    </div>
  );
}

/**
 * Timeline view with chart and dish selection.
 */
interface TimelineViewProps {
  viewMode: 'daily' | 'weekly';
  setViewMode: (mode: 'daily' | 'weekly') => void;
  selectedDishes: typeof DISH_DATA;
  allDishes: typeof DISH_DATA;
  onDishToggle: (id: string) => void;
  selectedIds: Set<string>;
}

function TimelineView({
  viewMode,
  setViewMode,
  selectedDishes,
  allDishes,
  onDishToggle,
  selectedIds,
}: TimelineViewProps) {
  return (
    <div className="timeline-view">
      {/* Timeline Chart */}
      <div className="timeline-chart-card">
        <div className="timeline-chart-header">
          <div>
            <h3 className="chart-title">Order Distribution Timeline</h3>
            <p className="chart-subtitle">
              Track how each dish sells over time. Click dishes below to compare.
            </p>
          </div>
          <div className="view-toggle">
            <button
              type="button"
              className={`view-toggle-btn ${viewMode === 'daily' ? 'active' : ''}`}
              onClick={() => setViewMode('daily')}
            >
              Daily
            </button>
            <button
              type="button"
              className={`view-toggle-btn ${viewMode === 'weekly' ? 'active' : ''}`}
              onClick={() => setViewMode('weekly')}
            >
              Weekly
            </button>
          </div>
        </div>

        <div className="timeline-chart-container">
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={TIMELINE_DATA}>
              <defs>
                {selectedDishes.map((dish) => (
                  <linearGradient
                    key={dish.id}
                    id={`gradient-${dish.id}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop offset="5%" stopColor={dish.color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={dish.color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'var(--color-text-primary)', fontWeight: 600 }}
              />
              <Legend
                wrapperStyle={{ paddingTop: '20px' }}
                formatter={(value) => (
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: '13px' }}>
                    {value}
                  </span>
                )}
              />
              {selectedIds.has('1') && (
                <Area
                  type="monotone"
                  dataKey="pizzaMargherita"
                  name="Pizza Margherita"
                  stroke="#dc2626"
                  fill="url(#gradient-1)"
                  strokeWidth={2}
                />
              )}
              {selectedIds.has('2') && (
                <Area
                  type="monotone"
                  dataKey="spaghettiCarbonara"
                  name="Spaghetti Carbonara"
                  stroke="#f59e0b"
                  fill="url(#gradient-2)"
                  strokeWidth={2}
                />
              )}
              {selectedIds.has('3') && (
                <Area
                  type="monotone"
                  dataKey="tiramisu"
                  name="Tiramisù"
                  stroke="#8b5cf6"
                  fill="url(#gradient-3)"
                  strokeWidth={2}
                />
              )}
              {selectedIds.has('4') && (
                <Area
                  type="monotone"
                  dataKey="risottoFunghi"
                  name="Risotto Funghi"
                  stroke="#22c55e"
                  fill="url(#gradient-4)"
                  strokeWidth={2}
                />
              )}
              {selectedIds.has('5') && (
                <Area
                  type="monotone"
                  dataKey="bruschetta"
                  name="Bruschetta"
                  stroke="#06b6d4"
                  fill="url(#gradient-5)"
                  strokeWidth={2}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Dish Selection Grid */}
      <div className="dish-selection">
        <h4 className="dish-selection-title">SELECT DISHES TO COMPARE (MAX 5)</h4>
        <div className="dish-grid">
          {allDishes.map((dish) => (
            <DishCard
              key={dish.id}
              dish={dish}
              isSelected={selectedIds.has(dish.id)}
              onToggle={() => onDishToggle(dish.id)}
            />
          ))}
        </div>
      </div>

      {/* Period Summary */}
      <div className="period-summary">
        <h4 className="period-summary-title">Period Summary</h4>
        <div className="period-summary-grid">
          <div className="period-stat">
            <span className="period-stat-value">{PERIOD_SUMMARY.totalItemsSold.toLocaleString()}</span>
            <span className="period-stat-label">Total Items Sold</span>
          </div>
          <div className="period-stat">
            <span className="period-stat-value">{PERIOD_SUMMARY.uniqueItems}</span>
            <span className="period-stat-label">Unique Items</span>
          </div>
          <div className="period-stat">
            <span className="period-stat-value">{PERIOD_SUMMARY.avgOrdersPerDay}</span>
            <span className="period-stat-label">Avg Orders/Day</span>
          </div>
          <div className="period-stat">
            <span className="period-stat-value">{PERIOD_SUMMARY.itemsTrendingUp}</span>
            <span className="period-stat-label">Items Trending Up</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Dish card component.
 */
interface DishCardProps {
  dish: (typeof DISH_DATA)[0];
  isSelected: boolean;
  onToggle: () => void;
}

function DishCard({ dish, isSelected, onToggle }: DishCardProps) {
  const trendIcon = dish.trend >= 0 ? '↗' : '↘';
  const trendClass = dish.trend >= 0 ? 'trend-up' : 'trend-down';

  return (
    <div
      className={`dish-card ${isSelected ? 'selected' : ''}`}
      onClick={onToggle}
      style={{ borderColor: isSelected ? dish.color : undefined }}
    >
      <div className="dish-card-header">
        <span className="dish-category">{dish.category}</span>
        <span className={`dish-trend-icon ${trendClass}`}>{trendIcon}</span>
      </div>
      <h5 className="dish-name">{dish.name}</h5>
      <div className="dish-stats">
        <span className="dish-orders">{dish.totalOrders.toLocaleString()}</span>
        <span className={`dish-trend ${trendClass}`}>
          {dish.trend >= 0 ? '+' : ''}
          {dish.trend}%
        </span>
      </div>
      <div className="dish-labels">
        <span className="dish-label">total orders</span>
        <span className="dish-label">trend</span>
      </div>
      <button type="button" className="dish-details-btn">
        View Details →
      </button>
    </div>
  );
}

/**
 * AI Insights view.
 */
function InsightsView() {
  return (
    <div className="insights-view">
      <div className="insights-grid">
        {AI_INSIGHTS.map((insight, index) => (
          <div key={index} className={`insight-card insight-${insight.type}`}>
            <div className="insight-header">
              <span className="insight-type-badge">{insight.type}</span>
              <h4 className="insight-title">{insight.title}</h4>
            </div>
            <p className="insight-description">{insight.description}</p>
            <div className="insight-impact">
              <span className="impact-label">Impact:</span>
              <span className="impact-value">{insight.impact}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Prep Summary view.
 */
function PrepSummaryView() {
  return (
    <div className="prep-view">
      <div className="prep-card">
        <h3 className="prep-title">Daily Prep Requirements</h3>
        <p className="prep-subtitle">Based on current demand patterns and forecasts</p>

        <div className="prep-table">
          <div className="prep-table-header">
            <span>Item</span>
            <span>Daily Needed</span>
            <span>Prep Time</span>
          </div>
          {PREP_SUMMARY.map((item, index) => (
            <div key={index} className="prep-table-row">
              <span className="prep-item-name">{item.item}</span>
              <span className="prep-item-quantity">
                {item.dailyNeeded} {item.unit}
              </span>
              <span className="prep-item-time">{item.prepTime}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="prep-tips">
        <h4 className="prep-tips-title">💡 Optimization Tips</h4>
        <ul className="prep-tips-list">
          <li>Batch pizza dough prep on slow mornings (Tue/Wed)</li>
          <li>Pre-portion tiramisù into individual servings for faster service</li>
          <li>Prepare extra risotto base on weekends (+20%)</li>
          <li>Fresh pasta can be made ahead and refrigerated for 24h</li>
        </ul>
      </div>
    </div>
  );
}
