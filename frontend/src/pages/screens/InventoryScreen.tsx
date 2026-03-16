/**
 * InventoryScreen - Main inventory management screen with OCR upload.
 *
 * Features:
 * - Current Inventory tab (reuses existing InventoryTab component)
 * - Purchase Orders tab
 * - Bills tab
 * - Documents History tab
 * - Document upload modal
 */
import React, { useState } from 'react';
import './InventoryScreen.css';
import { InventoryTab } from '../../components/InventoryTab';
import PurchaseOrdersTab from '../../components/inventory/PurchaseOrdersTab';
import BillsTab from '../../components/inventory/BillsTab';
import DocumentsHistoryTab from '../../components/inventory/DocumentsHistoryTab';
import DocumentUploadModal from '../../components/inventory/DocumentUploadModal';

type TabId = 'inventory' | 'purchase-orders' | 'bills' | 'documents';

interface Tab {
  id: TabId;
  label: string;
}

const TABS: Tab[] = [
  { id: 'inventory', label: 'Current Inventory' },
  { id: 'purchase-orders', label: 'Purchase Orders' },
  { id: 'bills', label: 'Bills' },
  { id: 'documents', label: 'Documents' }
];

const InventoryScreen: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('inventory');
  const [showUploadModal, setShowUploadModal] = useState(false);

  const renderTabContent = () => {
    switch (activeTab) {
      case 'inventory':
        return <InventoryTab />;
      case 'purchase-orders':
        return <PurchaseOrdersTab />;
      case 'bills':
        return <BillsTab />;
      case 'documents':
        return <DocumentsHistoryTab />;
      default:
        return null;
    }
  };

  const handleUploadSuccess = () => {
    // Refresh relevant tabs after successful upload
    // Implementation will trigger re-fetch in child components
    setShowUploadModal(false);
  };

  return (
    <div className="inventory-screen">
      <div className="inventory-header">
        <h2 className="inventory-title">Inventory</h2>
        <button
          className="btn btn-primary"
          onClick={() => setShowUploadModal(true)}
        >
          Upload Document
        </button>
      </div>

      <div className="inventory-tabs">
        <div className="inventory-tab-toggle">
          {TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              className={`inventory-tab-btn${activeTab === tab.id ? ' inventory-tab-btn--active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="inventory-tab-content">
        {renderTabContent()}
      </div>

      {showUploadModal && (
        <DocumentUploadModal
          onClose={() => setShowUploadModal(false)}
          onSuccess={handleUploadSuccess}
        />
      )}
    </div>
  );
};

export default InventoryScreen;
