import { useState } from 'react';
import StaffTab from './dashboard/StaffTab';
import CustomerTab from './dashboard/CustomerTab';
import KitchenTab from './dashboard/KitchenTab';
import CatalogueTab from './dashboard/CatalogueTab';
import './OutletDashboardWidget.css';

export default function OutletDashboardWidget() {
    const [activeTab, setActiveTab] = useState<'staff' | 'customer' | 'kitchen' | 'catalogue'>('staff');

    return (
        <div className="outlet-dashboard-widget">
            <div className="outlet-dashboard-header">
                <h3 className="outlet-dashboard-title">Outlet Dashboard</h3>
                <div className="outlet-dashboard-tabs">
                    <button
                        className={`outlet-dashboard-tab ${activeTab === 'staff' ? 'active' : ''}`}
                        onClick={() => setActiveTab('staff')}
                    >
                        Staff
                    </button>
                    <button
                        className={`outlet-dashboard-tab ${activeTab === 'customer' ? 'active' : ''}`}
                        onClick={() => setActiveTab('customer')}
                    >
                        Customer Exp
                    </button>
                    <button
                        className={`outlet-dashboard-tab ${activeTab === 'kitchen' ? 'active' : ''}`}
                        onClick={() => setActiveTab('kitchen')}
                    >
                        Kitchen
                    </button>
                    <button
                        className={`outlet-dashboard-tab ${activeTab === 'catalogue' ? 'active' : ''}`}
                        onClick={() => setActiveTab('catalogue')}
                    >
                        Catalogue
                    </button>
                </div>
            </div>

            <div className="outlet-dashboard-content">
                {activeTab === 'staff' && <StaffTab />}
                {activeTab === 'customer' && <CustomerTab />}
                {activeTab === 'kitchen' && <KitchenTab />}
                {activeTab === 'catalogue' && <CatalogueTab />}
            </div>
        </div>
    );
}
