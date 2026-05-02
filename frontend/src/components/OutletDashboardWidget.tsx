import CatalogueTab from './dashboard/CatalogueTab';
import './OutletDashboardWidget.css';

export default function OutletDashboardWidget() {
    return (
        <div className="outlet-dashboard-widget">
            <div className="outlet-dashboard-header">
                <h3 className="outlet-dashboard-title">Outlet Catalogue</h3>
            </div>

            <div className="outlet-dashboard-content">
                <CatalogueTab />
            </div>
        </div>
    );
}
