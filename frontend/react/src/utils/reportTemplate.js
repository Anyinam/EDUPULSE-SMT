const escapeHtml = (value) => {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
};

export const GRADE_SCALE_ROWS = [
  { grade: 'A', range: '80.0 - 100%', remark: 'EXCELLENT' },
  { grade: 'B', range: '70.0 - 79.9%', remark: 'VERY GOOD' },
  { grade: 'C', range: '60.0 - 69.9%', remark: 'GOOD' },
  { grade: 'D', range: '50.0 - 59.9%', remark: 'CREDIT' },
  { grade: 'E', range: '40.0 - 49.9%', remark: 'PASS' },
  { grade: 'F', range: '0.0 - 39.9%', remark: 'FAIL' }
];

export const getGradeFromTotal = (total) => {
  if (total >= 80) return 'A';
  if (total >= 70) return 'B';
  if (total >= 60) return 'C';
  if (total >= 50) return 'D';
  if (total >= 40) return 'E';
  return 'F';
};

export const getRemarkFromGrade = (grade) => {
  const scaleRow = GRADE_SCALE_ROWS.find((row) => row.grade === grade);
  return scaleRow?.remark || 'PENDING REVIEW';
};

export const formatGradingSchemeSummary = (classScoreMax = 30, examScoreMax = 70) => {
  return `Class Work ${classScoreMax}% • Exam ${examScoreMax}%`;
};

const buildSubjectTable = (subjectGrades) => {
  const rows = Array.isArray(subjectGrades) ? subjectGrades : [];
  if (rows.length === 0) {
    return '<div class="subject-empty">No subjects recorded.</div>';
  }

  const header = [
    'Subject',
    'Class',
    'Exam',
    'Total',
    'Grade',
    'Position',
    'Remarks'
  ].map((label) => `<th>${label}</th>`).join('');

  const body = rows.map((row) => {
    const subject = escapeHtml(row.subject ?? '');
    const classScore = escapeHtml(row.class_score ?? '');
    const examScore = escapeHtml(row.exam_score ?? '');
    const total = escapeHtml(row.total ?? '');
    const grade = escapeHtml(row.grade ?? '');
    const position = escapeHtml(row.position ?? '');
    const remarks = escapeHtml(row.remarks ?? '');
    return `
      <tr>
        <td>${subject}</td>
        <td>${classScore}</td>
        <td>${examScore}</td>
        <td>${total}</td>
        <td>${grade}</td>
        <td>${position}</td>
        <td>${remarks}</td>
      </tr>
    `;
  }).join('');

  return `
    <table class="subject-table">
      <thead>
        <tr>${header}</tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
};

export const buildTemplateHtml = ({ templateConfig, data }) => {
  if (!templateConfig || templateConfig.type !== 'html' || !templateConfig.html) {
    return '';
  }

  const showHeadmasterRemarks = templateConfig?.visibility?.show_headmaster_remarks !== false;

  const subjectTable = buildSubjectTable(data.subject_grades || []);
  const safeData = { ...data, subject_table: subjectTable };

  Object.keys(safeData).forEach((key) => {
    if (key === 'subject_table') return;
    safeData[key] = escapeHtml(safeData[key] ?? '');
  });

  const compiledHtml = templateConfig.html.replace(/{{\s*([a-zA-Z0-9_]+)\s*}}/g, (match, key) => {
    return key in safeData ? safeData[key] : '';
  });

  const backgroundImage = templateConfig.background_image
    ? `background-image: url('${templateConfig.background_image}'); background-size: cover; background-repeat: no-repeat;`
    : '';

  const templateCss = `${templateConfig.css || ''}
    ${showHeadmasterRemarks ? '' : '.headmaster-remarks { display: none !important; }'}
  `;

  return `
    <style>
      ${templateCss}
    </style>
    <div class="report-template" style="${backgroundImage}">
      ${compiledHtml}
    </div>
  `;
};
