import './InsightsCard.css';

export default function KitchenInsights() {
    return (
        <div className="insights-card">
            <div className="insights-icon">
                <svg fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                </svg>
            </div>
            <div className="insights-content">
                <h3>Kitchen Efficiency</h3>
                <p>Average prep time today is <strong>12m</strong>. Current load is <strong className="text-success">Manageable</strong>.</p>
                <p>Trending item: <strong>Truffle Pasta</strong> (Low inventory warning).</p>
            </div>
        </div>
    );
}
