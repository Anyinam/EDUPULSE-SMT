import gradmanV1 from './gradman_v1.json';
import parentFocus from './parent_focus.json';
import progressInsights from './progress_insights.json';
import compactClear from './compact_clear.json';
import guardianNarrative from './guardian_narrative.json';

const reportTemplates = [
  {
    id: gradmanV1.id,
    name: gradmanV1.name,
    description: gradmanV1.description,
    config: gradmanV1.config
  },
  {
    id: parentFocus.id,
    name: parentFocus.name,
    description: parentFocus.description,
    config: parentFocus.config
  },
  {
    id: progressInsights.id,
    name: progressInsights.name,
    description: progressInsights.description,
    config: progressInsights.config
  },
  {
    id: compactClear.id,
    name: compactClear.name,
    description: compactClear.description,
    config: compactClear.config
  },
  {
    id: guardianNarrative.id,
    name: guardianNarrative.name,
    description: guardianNarrative.description,
    config: guardianNarrative.config
  }
];

export default reportTemplates;
