import { useState } from 'react';
import StaffTab from './dashboard/StaffTab';
import CustomerTab from './dashboard/CustomerTab';
import KitchenTab from './dashboard/KitchenTab';
import CatalogueTab from './dashboard/CatalogueTab';
import './OperationsDashboardWidget.css';

export default function OperationsDashboardWidget() {
    const [activeTab, setActiveTab] = useState<'staff' | 'customer' | 'kitchen' | 'catalogue'>('staff');

    return (
        <div className="ops-dashboard-widget">
            <div className="ops-dashboard-header">
                <h3 className="ops-dashboard-title">Operations Dashboard</h3>
                <div className="ops-dashboard-tabs">
                    <button
                        className={`ops-dashboard-tab ${activeTab === 'staff' ? 'active' : ''}`}
                        onClick={() => setActiveTab('staff')}
                    >
                        Staff
                    </button>
                    <button
                        className={`ops-dashboard-tab ${activeTab === 'customer' ? 'active' : ''}`}
                        onClick={() => setActiveTab('customer')}
                    >
                        Customer Exp
                    </button>
                    <button
                        className={`ops-dashboard-tab ${activeTab === 'kitchen' ? 'active' : ''}`}
                        onClick={() => setActiveTab('kitchen')}
                    >
                        Kitchen
                    </button>
                    <button
                        className={`ops-dashboard-tab ${activeTab === 'catalogue' ? 'active' : ''}`}
                        onClick={() => setActiveTab('catalogue')}
                    >
                        Catalogue
                    </button>
                </div>
            </div>

            <div className="ops-dashboard-content">
                {activeTab === 'staff' && <StaffTab />}
                {activeTab === 'customer' && <CustomerTab />}
                {activeTab === 'kitchen' && <KitchenTab />}
                {activeTab === 'catalogue' && <CatalogueTab />}
            </div>
        </div>
    );
}
