import fs from 'fs';
import path from 'path';
import { db } from '../models/database';

interface TestImporter {
  importTest(filePath: string): Promise<void>;
}

interface ImportStats {
  testsImported: number;
  problemsImported: number;
  solutionsImported: number;
  tagsCreated: number;
  errors: string[];
}

// Generic Tag Manager
class TagManager {
  private tagCache: Map<string, string> = new Map(); // name -> id

  async ensureTag(name: string, category: string, color?: string): Promise<string> {
    const normalizedName = name.toLowerCase().trim();

    if (this.tagCache.has(normalizedName)) {
      return this.tagCache.get(normalizedName)!;
    }

    const result = await db.query(
      `INSERT INTO tags (name, category, color)
       VALUES ($1, $2, $3)
       ON CONFLICT (name) DO UPDATE SET category = EXCLUDED.category
       RETURNING id`,
      [normalizedName, category, color || '#667eea']
    );

    const tagId = result.rows[0].id;
    this.tagCache.set(normalizedName, tagId);
    return tagId;
  }

  async ensureMultipleTags(tags: Array<{ name: string; category: string; color?: string }>): Promise<string[]> {
    const tagIds: string[] = [];
    for (const tag of tags) {
      const tagId = await this.ensureTag(tag.name, tag.category, tag.color);
      tagIds.push(tagId);
    }
    return tagIds;
  }
}

// AMC Test Importer
class AmcTestImporter implements TestImporter {
  private tagManager: TagManager;
  private stats: ImportStats;

  constructor(tagManager: TagManager, stats: ImportStats) {
    this.tagManager = tagManager;
    this.stats = stats;
  }

  async importTest(filePath: string): Promise<void> {
    console.log(`Importing AMC test from: ${filePath}`);

    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));

    try {
      // 1. Ensure test category exists
      const categoryId = await this.ensureCategory('amc', 'American Mathematics Competition');

      // 2. Create or get test
      const testId = await this.createTest(categoryId, data.metadata);

      // 3. Import problems
      for (const problem of data.problems) {
        try {
          await this.importProblem(testId, problem);
          this.stats.problemsImported++;
        } catch (error: any) {
          this.stats.errors.push(`Problem ${problem.problemNumber}: ${error.message}`);
        }
      }

      this.stats.testsImported++;
      console.log(`✓ Imported: ${data.metadata.year} ${data.metadata.test}`);
    } catch (error: any) {
      this.stats.errors.push(`Test import failed: ${error.message}`);
      throw error;
    }
  }

  private async ensureCategory(name: string, displayName: string): Promise<string> {
    const result = await db.query(
      `INSERT INTO test_categories (name, display_name, description)
       VALUES ($1, $2, $3)
       ON CONFLICT (name) DO UPDATE SET display_name = EXCLUDED.display_name
       RETURNING id`,
      [name, displayName, `${displayName} standardized test problems`]
    );
    return result.rows[0].id;
  }

  private async createTest(categoryId: string, metadata: any): Promise<string> {
    const result = await db.query(
      `INSERT INTO tests (category_id, name, year, variant, problem_count, source_url, crawled_at, metadata)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT ON CONSTRAINT tests_pkey DO NOTHING
       RETURNING id`,
      [
        categoryId,
        `${metadata.year} ${metadata.test}`,
        metadata.year,
        metadata.test.includes('10A') ? 'A' : metadata.test.includes('10B') ? 'B' : metadata.test.includes('Fall') ? 'Fall' : null,
        metadata.totalProblems,
        metadata.source,
        metadata.crawledAt,
        JSON.stringify(metadata)
      ]
    );

    // If test already exists, fetch its ID
    if (result.rows.length === 0) {
      const existingTest = await db.query(
        `SELECT id FROM tests WHERE name = $1 AND year = $2`,
        [`${metadata.year} ${metadata.test}`, metadata.year]
      );
      return existingTest.rows[0].id;
    }

    return result.rows[0].id;
  }

  private async importProblem(testId: string, problem: any): Promise<void> {
    // Create problem
    const problemResult = await db.query(
      `INSERT INTO test_problems (
        test_id, problem_number, content, difficulty, images, answer_choices_image, metadata
      ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      ON CONFLICT (test_id, problem_number) DO UPDATE
      SET content = EXCLUDED.content,
          difficulty = EXCLUDED.difficulty
      RETURNING id`,
      [
        testId,
        problem.problemNumber,
        problem.content,
        problem.difficulty || 'medium',
        problem.images || [],
        problem.answerChoicesImage || null,
        JSON.stringify({
          year: problem.year,
          test: problem.test,
          seeAlso: problem.seeAlso || []
        })
      ]
    );

    const problemId = problemResult.rows[0].id;

    // Extract and create tags
    const tags = await this.extractTags(problem);
    await this.addTagsToProblem(problemId, tags);

    // Import choices
    if (problem.choices && problem.choices.length > 0) {
      await this.importChoices(problemId, problem.choices);
    }

    // Import solutions
    if (problem.solutions && problem.solutions.length > 0) {
      await this.importSolutions(problemId, problem.solutions);
    }
  }

  private async extractTags(problem: any): Promise<string[]> {
    const tagData: Array<{ name: string; category: string; color?: string }> = [];

    // Add difficulty tag
    if (problem.difficulty) {
      tagData.push({
        name: problem.difficulty,
        category: 'difficulty',
        color: problem.difficulty === 'easy' ? '#28a745' : problem.difficulty === 'hard' ? '#dc3545' : '#ffc107'
      });
    }

    // Add year tag
    if (problem.year) {
      tagData.push({
        name: `year-${problem.year}`,
        category: 'year',
        color: '#6c757d'
      });
    }

    // Add test-specific tags
    if (problem.test) {
      tagData.push({
        name: `amc-10${problem.test.toLowerCase()}`,
        category: 'test-variant',
        color: '#667eea'
      });
    }

    // Extract topic tags
    if (problem.topics && Array.isArray(problem.topics)) {
      for (const topic of problem.topics) {
        if (topic && topic.trim() && topic.toLowerCase() !== 'category') {
          const normalizedTopic = topic.toLowerCase().replace(/\s+/g, '-');
          tagData.push({
            name: normalizedTopic,
            category: 'topic',
            color: '#17a2b8'
          });
        }
      }
    }

    // Auto-detect subject tags from content
    const contentLower = problem.content.toLowerCase();

    if (this.containsAlgebraKeywords(contentLower)) {
      tagData.push({ name: 'algebra', category: 'subject', color: '#007bff' });
    }
    if (this.containsGeometryKeywords(contentLower)) {
      tagData.push({ name: 'geometry', category: 'subject', color: '#6f42c1' });
    }
    if (this.containsProbabilityKeywords(contentLower)) {
      tagData.push({ name: 'probability', category: 'subject', color: '#e83e8c' });
    }
    if (this.containsNumberTheoryKeywords(contentLower)) {
      tagData.push({ name: 'number-theory', category: 'subject', color: '#fd7e14' });
    }
    if (this.containsCombinatoricsKeywords(contentLower)) {
      tagData.push({ name: 'combinatorics', category: 'subject', color: '#20c997' });
    }

    return await this.tagManager.ensureMultipleTags(tagData);
  }

  private containsAlgebraKeywords(content: string): boolean {
    const keywords = ['equation', 'variable', 'solve', 'polynomial', 'quadratic', 'linear', 'expression', 'simplify', 'factor'];
    return keywords.some(kw => content.includes(kw));
  }

  private containsGeometryKeywords(content: string): boolean {
    const keywords = ['triangle', 'circle', 'rectangle', 'square', 'angle', 'area', 'perimeter', 'radius', 'diameter', 'polygon', 'vertex', 'side'];
    return keywords.some(kw => content.includes(kw));
  }

  private containsProbabilityKeywords(content: string): boolean {
    const keywords = ['probability', 'chance', 'random', 'expected', 'coin', 'dice', 'outcomes'];
    return keywords.some(kw => content.includes(kw));
  }

  private containsNumberTheoryKeywords(content: string): boolean {
    const keywords = ['prime', 'divisible', 'factor', 'multiple', 'remainder', 'modulo', 'gcd', 'lcm', 'integer'];
    return keywords.some(kw => content.includes(kw));
  }

  private containsCombinatoricsKeywords(content: string): boolean {
    const keywords = ['combination', 'permutation', 'arrange', 'ways to', 'select', 'choose'];
    return keywords.some(kw => content.includes(kw));
  }

  private async addTagsToProblem(problemId: string, tagIds: string[]): Promise<void> {
    for (const tagId of tagIds) {
      try {
        await db.query(
          `INSERT INTO problem_tags (problem_id, tag_id)
           VALUES ($1, $2)
           ON CONFLICT (problem_id, tag_id) DO NOTHING`,
          [problemId, tagId]
        );
        this.stats.tagsCreated++;
      } catch (error) {
        // Ignore duplicate errors
      }
    }
  }

  private async importChoices(problemId: string, choices: string[]): Promise<void> {
    const labels = ['A', 'B', 'C', 'D', 'E'];

    for (let i = 0; i < choices.length; i++) {
      if (choices[i] && choices[i].trim()) {
        await db.query(
          `INSERT INTO answer_choices (problem_id, choice_label, choice_text, choice_order)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT ON CONSTRAINT answer_choices_pkey DO NOTHING`,
          [problemId, labels[i] || `${i + 1}`, choices[i], i + 1]
        );
      }
    }
  }

  private async importSolutions(problemId: string, solutions: string[]): Promise<void> {
    for (let i = 0; i < solutions.length; i++) {
      if (solutions[i] && solutions[i].trim()) {
        // Skip video links
        if (solutions[i].startsWith('http')) {
          continue;
        }

        await db.query(
          `INSERT INTO problem_solutions (problem_id, solution_text, solution_order, is_official)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT ON CONSTRAINT problem_solutions_pkey DO NOTHING`,
          [problemId, solutions[i], i + 1, i === 0] // First solution is usually official
        );
        this.stats.solutionsImported++;
      }
    }
  }
}

// Main import orchestrator
async function importAllTests(dataDir: string = 'crawled_data'): Promise<ImportStats> {
  const stats: ImportStats = {
    testsImported: 0,
    problemsImported: 0,
    solutionsImported: 0,
    tagsCreated: 0,
    errors: []
  };

  const tagManager = new TagManager();

  try {
    // Read index file
    const indexPath = path.join(dataDir, 'amc_index.json');

    if (!fs.existsSync(indexPath)) {
      throw new Error(`Index file not found: ${indexPath}`);
    }

    const indexData = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));

    console.log(`Found ${indexData.tests.length} tests to import`);

    // Import each test
    const amcImporter = new AmcTestImporter(tagManager, stats);

    for (const test of indexData.tests) {
      const testFilePath = path.join(dataDir, path.basename(test.filePath));

      if (!fs.existsSync(testFilePath)) {
        stats.errors.push(`File not found: ${testFilePath}`);
        continue;
      }

      try {
        await amcImporter.importTest(testFilePath);
      } catch (error: any) {
        console.error(`Failed to import ${testFilePath}:`, error.message);
      }
    }

    return stats;
  } catch (error: any) {
    console.error('Import failed:', error);
    stats.errors.push(`Fatal error: ${error.message}`);
    return stats;
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);
  const dataDir = args[0] || 'crawled_data';

  console.log('===================================');
  console.log('Test Data Importer');
  console.log('===================================\n');

  const startTime = Date.now();

  const stats = await importAllTests(dataDir);

  const duration = ((Date.now() - startTime) / 1000).toFixed(2);

  console.log('\n===================================');
  console.log('Import Summary');
  console.log('===================================');
  console.log(`✓ Tests imported: ${stats.testsImported}`);
  console.log(`✓ Problems imported: ${stats.problemsImported}`);
  console.log(`✓ Solutions imported: ${stats.solutionsImported}`);
  console.log(`✓ Tags created: ${stats.tagsCreated}`);
  console.log(`✗ Errors: ${stats.errors.length}`);
  console.log(`⏱  Duration: ${duration}s`);

  if (stats.errors.length > 0) {
    console.log('\nErrors:');
    stats.errors.slice(0, 10).forEach(err => console.log(`  - ${err}`));
    if (stats.errors.length > 10) {
      console.log(`  ... and ${stats.errors.length - 10} more`);
    }
  }

  process.exit(0);
}

// Run if called directly
if (require.main === module) {
  main().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

export { importAllTests, AmcTestImporter, TagManager };
