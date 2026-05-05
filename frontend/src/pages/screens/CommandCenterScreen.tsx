/**
 * Command Center — Chat interface.
 * Reads ?insightId=... from the URL so the Intelligence Hub can open a
 * pre-seeded insight conversation without a separate route.
 */

import { useSearchParams } from 'react-router-dom';
import ChatbotPage from '../ChatbotPage';
import './CommandCenterScreen.css';

export default function CommandCenterScreen() {
  const [searchParams] = useSearchParams();
  const insightId = searchParams.get('insightId') ?? undefined;
  const insightHeadline = searchParams.get('insightHeadline') ?? undefined;

  return (
    <div className="cc-screen">
      <ChatbotPage insightId={insightId} insightHeadline={insightHeadline} />
    </div>
  );
}
