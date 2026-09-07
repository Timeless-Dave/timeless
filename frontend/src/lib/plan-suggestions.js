/** @typedef {{ key: string, label: string, outcome: string, nextStep: string }} GoalTemplate */

const CORE_TEMPLATES = {
  code: {
    key: 'code',
    label: 'Ship code',
    outcome: 'Land one meaningful code change',
    nextStep: 'Open the repo and write the first failing test',
  },
  leetcode: {
    key: 'leetcode',
    label: 'LeetCode',
    outcome: 'Finish one timed practice problem',
    nextStep: 'Pick one medium problem and start a 25-minute timer',
  },
  coursera: {
    key: 'coursera',
    label: 'Coursera',
    outcome: 'Complete one Coursera module segment',
    nextStep: 'Open the next lesson or quiz and press start',
  },
  algorithms: {
    key: 'algorithms',
    label: 'Algorithms',
    outcome: 'Advance algorithms study for today',
    nextStep: 'Work through one example, proof, or exercise set',
  },
  applications: {
    key: 'applications',
    label: 'Applications',
    outcome: 'Move one application forward',
    nextStep: 'Update one posting, send one email, or submit one form',
  },
  reading: {
    key: 'reading',
    label: 'Reading',
    outcome: 'Finish one focused reading block',
    nextStep: 'Open the paper or chapter and read without switching tabs',
  },
  writing: {
    key: 'writing',
    label: 'Writing',
    outcome: 'Produce one writing draft',
    nextStep: 'Write the opening paragraph or bullet outline',
  },
  'review-notes': {
    key: 'review-notes',
    label: 'Review notes',
    outcome: 'Consolidate notes from one topic',
    nextStep: 'Summarize one lecture or section in your own words',
  },
};

const PRESET_ALIASES = {
  Code: 'code',
  LeetCode: 'leetcode',
  Coursera: 'coursera',
  Algorithms: 'algorithms',
  Applications: 'applications',
  Reading: 'reading',
  Writing: 'writing',
  'Review notes': 'review-notes',
};

function slugify(label) {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'course';
}

/** Turn a course or unknown preset label into an outcome + next action pair. */
export function courseTemplate(label) {
  const key = slugify(label);
  return {
    key,
    label,
    outcome: `Make measurable progress in ${label}`,
    nextStep: 'Open the course and complete one concrete assignment item',
  };
}

export function resolveTemplate(label) {
  const alias = PRESET_ALIASES[label];
  if (alias && CORE_TEMPLATES[alias]) return CORE_TEMPLATES[alias];
  const direct = slugify(label);
  if (CORE_TEMPLATES[direct]) return CORE_TEMPLATES[direct];
  return courseTemplate(label);
}

/** Deduplicated quick-start templates derived from academics presets. */
export function templatesForAcademics(academics) {
  const seen = new Set();
  const list = [];
  for (const preset of academics?.presets || []) {
    const template = resolveTemplate(preset);
    if (seen.has(template.key)) continue;
    seen.add(template.key);
    list.push(template);
  }
  return list;
}

export { CORE_TEMPLATES };
