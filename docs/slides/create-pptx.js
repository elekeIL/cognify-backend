const pptxgen = require('pptxgenjs');
const path = require('path');

// Get html2pptx path
const html2pptxPath = path.join(
  process.env.USERPROFILE || process.env.HOME,
  '.claude/plugins/cache/anthropic-agent-skills/document-skills/00756142ab04/skills/pptx/scripts/html2pptx.js'
);
const html2pptx = require(html2pptxPath);

async function createPresentation() {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'Engineering Team';
  pptx.title = 'Cognify - Technical Interview Presentation';
  pptx.subject = 'Full-Stack Engineer Technical Challenge';

  const slidesDir = __dirname;

  // Create all 5 slides
  console.log('Creating slide 1: Title...');
  await html2pptx(path.join(slidesDir, 'slide1.html'), pptx);

  console.log('Creating slide 2: Problem...');
  await html2pptx(path.join(slidesDir, 'slide2.html'), pptx);

  console.log('Creating slide 3: Approach...');
  await html2pptx(path.join(slidesDir, 'slide3.html'), pptx);

  console.log('Creating slide 4: Stack...');
  await html2pptx(path.join(slidesDir, 'slide4.html'), pptx);

  console.log('Creating slide 5: Risks & Roadmap...');
  await html2pptx(path.join(slidesDir, 'slide5.html'), pptx);

  // Save the presentation
  const outputPath = path.join(slidesDir, '..', 'Cognify_Presentation.pptx');
  await pptx.writeFile({ fileName: outputPath });
  console.log(`Presentation saved to: ${outputPath}`);
}

createPresentation().catch(err => {
  console.error('Error creating presentation:', err);
  process.exit(1);
});
