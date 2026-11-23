/**
 * Pilot importer for MATHCOUNTS Tests (issue #14). Throwaway: it exists to
 * prove the crawled_data format from #12 against the schema from #11 on a
 * scratch database, before the real MathcountsTestImporter is built.
 *
 *   DATABASE_URL=postgresql://.../sbuddy_pilot \
 *     npx ts-node scripts/mathcounts/pilotImport.ts crawled_data/mathcounts
 *
 * It refuses to run unless the database name contains "pilot", because it
 * applies the #11 schema change (round, answer_unit, answer_alternatives and
 * the (test_id, round, problem_number) key) that the app does not know yet.
 */
import fs from 'fs';
import path from 'path';
import { db, initializeDatabase, redis } from '../../src/models/database';

interface McProblem {
  round: string;
  problemNumber: number;
  content: string;
  answer: string;
  answerUnit?: string;
  answerAlternatives?: string[];
  solutions: string[];
  images: string[];
}

interface McTest {
  metadata: { competition: string; year: number; variant: string; name: string; [k: string]: unknown };
  problems: McProblem[];
}

const MIGRATION = [
  `ALTER TABLE test_problems ADD COLUMN IF NOT EXISTS round TEXT`,
  `ALTER TABLE test_problems ADD COLUMN IF NOT EXISTS answer_unit TEXT`,
  `ALTER TABLE test_problems ADD COLUMN IF NOT EXISTS answer_alternatives TEXT[]`,
  `ALTER TABLE test_problems DROP CONSTRAINT IF EXISTS test_problems_test_id_problem_number_key`,
  `DO $$ BEGIN
     IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'test_problems_test_round_number_key') THEN
       ALTER TABLE test_problems ADD CONSTRAINT test_problems_test_round_number_key
         UNIQUE NULLS NOT DISTINCT (test_id, round, problem_number);
     END IF;
   END $$`,
];

function publicUrl(testDir: string, rel: string): string {
  return rel.replace(/^figures\//, `/test-images/mathcounts/${testDir}/`);
}

async function importTest(dir: string, testDir: string) {
  const test: McTest = JSON.parse(fs.readFileSync(path.join(dir, 'test.json'), 'utf-8'));
  const m = test.metadata;

  // Figures -> public/, which express.static already serves.
  const figSrc = path.join(dir, 'figures');
  const figDst = path.join('public', 'test-images', 'mathcounts', testDir);
  if (fs.existsSync(figSrc)) {
    fs.mkdirSync(figDst, { recursive: true });
    for (const f of fs.readdirSync(figSrc)) fs.copyFileSync(path.join(figSrc, f), path.join(figDst, f));
  }

  const cat = await db.query(
    `INSERT INTO test_categories (name, display_name, description) VALUES ('mathcounts', 'MATHCOUNTS', 'MATHCOUNTS competition problems')
     ON CONFLICT (name) DO UPDATE SET display_name = EXCLUDED.display_name RETURNING id`
  );
  const categoryId = cat.rows[0].id;

  const existing = await db.query(`SELECT id FROM tests WHERE category_id = $1 AND name = $2`, [categoryId, m.name]);
  let testId: string;
  if (existing.rows.length) {
    testId = existing.rows[0].id;
    await db.query(
      `UPDATE tests SET year = $2, variant = $3, problem_count = $4, metadata = $5, updated_at = NOW() WHERE id = $1`,
      [testId, m.year, m.variant, test.problems.length, JSON.stringify(m)]
    );
  } else {
    const ins = await db.query(
      `INSERT INTO tests (category_id, name, year, variant, problem_count, metadata, crawled_at)
       VALUES ($1, $2, $3, $4, $5, $6, NOW()) RETURNING id`,
      [categoryId, m.name, m.year, m.variant, test.problems.length, JSON.stringify(m)]
    );
    testId = ins.rows[0].id;
  }

  let upserted = 0, solutions = 0;
  const seen = new Set<string>();
  for (const p of test.problems) {
    seen.add(`${p.round}-${p.problemNumber}`);
    const row = await db.query(
      `INSERT INTO test_problems (test_id, round, problem_number, content, correct_answer, answer_unit, answer_alternatives, images)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT ON CONSTRAINT test_problems_test_round_number_key DO UPDATE SET
         content = EXCLUDED.content, correct_answer = EXCLUDED.correct_answer,
         answer_unit = EXCLUDED.answer_unit, answer_alternatives = EXCLUDED.answer_alternatives,
         images = EXCLUDED.images, updated_at = NOW()
       RETURNING id`,
      [testId, p.round, p.problemNumber, p.content, p.answer, p.answerUnit ?? null,
       p.answerAlternatives ?? [], p.images.map(i => publicUrl(testDir, i))]
    );
    const problemId = row.rows[0].id;
    upserted++;

    // Zero or one official solution: update it in place so its id is stable too.
    const text = p.solutions[0];
    if (text) {
      const sol = text.replace(/\[DIAGRAM:\s*(figures\/[^\]\s]+)\]/g, (_, rel) => `[DIAGRAM: ${publicUrl(testDir, rel)}]`);
      const upd = await db.query(
        `UPDATE problem_solutions SET solution_text = $2, updated_at = NOW()
         WHERE problem_id = $1 AND is_official AND solution_order = 1`,
        [problemId, sol]
      );
      if (upd.rowCount === 0) {
        await db.query(
          `INSERT INTO problem_solutions (problem_id, solution_text, solution_order, is_official) VALUES ($1, $2, 1, TRUE)`,
          [problemId, sol]
        );
      }
      solutions++;
    }
  }

  // Never delete: report Problems that are in the DB but no longer in the file.
  const inDb = await db.query(`SELECT round, problem_number FROM test_problems WHERE test_id = $1`, [testId]);
  const orphans = inDb.rows.filter(r => !seen.has(`${r.round}-${r.problem_number}`));
  console.log(`✓ ${m.name}: ${upserted} problems, ${solutions} solutions` +
    (orphans.length ? `, ${orphans.length} in DB but not in file (kept)` : ''));
}

async function main() {
  const root = process.argv[2] || 'crawled_data/mathcounts';
  const dbName = new URL(process.env.DATABASE_URL || '').pathname.slice(1);
  if (!dbName.includes('pilot')) {
    throw new Error(`refusing to migrate "${dbName}": point DATABASE_URL at a scratch *pilot* database`);
  }
  await initializeDatabase();
  for (const sql of MIGRATION) await db.query(sql);

  if (!fs.existsSync(root)) return console.log(`no ${root}, nothing to import`);
  for (const testDir of fs.readdirSync(root).sort()) {
    const dir = path.join(root, testDir);
    if (testDir.startsWith('_') || !fs.existsSync(path.join(dir, 'test.json'))) continue;
    await importTest(dir, testDir);
  }
}

main()
  .catch(err => { console.error(err); process.exitCode = 1; })
  // initializeDatabase() checks out a pool client it never releases, so
  // db.end() would wait forever; exit explicitly instead.
  .finally(async () => { if (redis.isOpen) await redis.quit(); process.exit(); });
