import { db } from '../models/database';

export interface TestCategory {
  id: string;
  name: string;
  displayName: string;
  description?: string;
  iconUrl?: string;
  testCount?: number;
  problemCount?: number;
}

export interface Test {
  id: string;
  categoryId: string;
  categoryName?: string;
  name: string;
  year?: number;
  variant?: string;
  problemCount: number;
  sourceUrl?: string;
  metadata?: any;
  crawledAt?: Date;
}

export interface Tag {
  id: string;
  name: string;
  category: string;
  description?: string;
  color?: string;
  usageCount?: number;
}

export interface Problem {
  id: string;
  testId: string;
  testName?: string;
  problemNumber: number;
  title?: string;
  content: string;
  difficulty: string;
  points?: number;
  timeLimit?: number;
  images?: string[];
  answerChoicesImage?: string;
  correctAnswer?: string;
  explanation?: string;
  tags?: Tag[];
  choices?: AnswerChoice[];
  solutions?: Solution[];
  relatedProblems?: RelatedProblem[];
}

export interface AnswerChoice {
  id: string;
  choiceLabel: string;
  choiceText: string;
  choiceOrder: number;
  isCorrect?: boolean;
}

export interface Solution {
  id: string;
  solutionText: string;
  solutionOrder: number;
  author?: string;
  upvotes: number;
  isOfficial: boolean;
}

export interface RelatedProblem {
  id: string;
  problemNumber: number;
  testName: string;
  relationshipType: string;
}

export interface SearchFilters {
  tags?: string[];
  difficulty?: string;
  testCategoryId?: string;
  testId?: string;
  year?: number;
  searchQuery?: string;
  page?: number;
  limit?: number;
}

export interface PaginatedResult<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export interface SearchFacets {
  tags: Array<{ name: string; count: number }>;
  difficulties: Array<{ level: string; count: number }>;
  years: Array<{ year: number; count: number }>;
}

export class TestViewerService {
  // ============ Test Categories ============
  async getAllCategories(): Promise<TestCategory[]> {
    const result = await db.query(`
      SELECT
        tc.id,
        tc.name,
        tc.display_name as "displayName",
        tc.description,
        tc.icon_url as "iconUrl",
        COUNT(DISTINCT t.id) as "testCount",
        COUNT(DISTINCT tp.id) as "problemCount"
      FROM test_categories tc
      LEFT JOIN tests t ON tc.id = t.category_id
      LEFT JOIN test_problems tp ON t.id = tp.test_id
      GROUP BY tc.id, tc.name, tc.display_name, tc.description, tc.icon_url
      ORDER BY tc.name
    `);
    return result.rows;
  }

  async getCategoryById(categoryId: string): Promise<TestCategory | null> {
    const result = await db.query(`
      SELECT
        tc.id,
        tc.name,
        tc.display_name as "displayName",
        tc.description,
        tc.icon_url as "iconUrl",
        COUNT(DISTINCT t.id) as "testCount",
        COUNT(DISTINCT tp.id) as "problemCount"
      FROM test_categories tc
      LEFT JOIN tests t ON tc.id = t.category_id
      LEFT JOIN test_problems tp ON t.id = tp.test_id
      WHERE tc.id = $1
      GROUP BY tc.id, tc.name, tc.display_name, tc.description, tc.icon_url
    `, [categoryId]);

    return result.rows[0] || null;
  }

  // ============ Tests ============
  async getTestsByCategory(categoryId: string, filters?: { year?: number; variant?: string }): Promise<Test[]> {
    let query = `
      SELECT
        t.id,
        t.category_id as "categoryId",
        tc.display_name as "categoryName",
        t.name,
        t.year,
        t.variant,
        t.problem_count as "problemCount",
        t.source_url as "sourceUrl",
        t.metadata,
        t.crawled_at as "crawledAt"
      FROM tests t
      JOIN test_categories tc ON t.category_id = tc.id
      WHERE t.category_id = $1
    `;

    const params: any[] = [categoryId];
    let paramCount = 1;

    if (filters?.year) {
      paramCount++;
      query += ` AND t.year = $${paramCount}`;
      params.push(filters.year);
    }

    if (filters?.variant) {
      paramCount++;
      query += ` AND t.variant = $${paramCount}`;
      params.push(filters.variant);
    }

    query += ` ORDER BY t.year DESC, t.variant`;

    const result = await db.query(query, params);
    return result.rows;
  }

  async getTestById(testId: string): Promise<Test | null> {
    const result = await db.query(`
      SELECT
        t.id,
        t.category_id as "categoryId",
        tc.display_name as "categoryName",
        t.name,
        t.year,
        t.variant,
        t.problem_count as "problemCount",
        t.source_url as "sourceUrl",
        t.metadata,
        t.crawled_at as "crawledAt"
      FROM tests t
      JOIN test_categories tc ON t.category_id = tc.id
      WHERE t.id = $1
    `, [testId]);

    return result.rows[0] || null;
  }

  // ============ Tags ============
  async getAllTags(filters?: { category?: string; search?: string }): Promise<Tag[]> {
    let query = `
      SELECT
        t.id,
        t.name,
        t.category,
        t.description,
        t.color,
        COUNT(pt.problem_id) as "usageCount"
      FROM tags t
      LEFT JOIN problem_tags pt ON t.id = pt.tag_id
    `;

    const params: any[] = [];
    const whereClauses: string[] = [];

    if (filters?.category) {
      params.push(filters.category);
      whereClauses.push(`t.category = $${params.length}`);
    }

    if (filters?.search) {
      params.push(`%${filters.search}%`);
      whereClauses.push(`t.name ILIKE $${params.length}`);
    }

    if (whereClauses.length > 0) {
      query += ` WHERE ${whereClauses.join(' AND ')}`;
    }

    query += ` GROUP BY t.id, t.name, t.category, t.description, t.color ORDER BY "usageCount" DESC, t.name`;

    const result = await db.query(query, params);
    return result.rows;
  }

  // ============ Problems ============
  async getProblemsByTest(testId: string, filters?: SearchFilters): Promise<PaginatedResult<Problem>> {
    const page = filters?.page || 1;
    const limit = filters?.limit || 25;
    const offset = (page - 1) * limit;

    let query = `
      SELECT
        tp.id,
        tp.test_id as "testId",
        t.name as "testName",
        tp.problem_number as "problemNumber",
        tp.title,
        tp.content,
        tp.difficulty,
        tp.points,
        tp.time_limit as "timeLimit",
        tp.images,
        tp.answer_choices_image as "answerChoicesImage",
        tp.correct_answer as "correctAnswer",
        tp.explanation
      FROM test_problems tp
      JOIN tests t ON tp.test_id = t.id
      WHERE tp.test_id = $1
    `;

    const params: any[] = [testId];
    let paramCount = 1;

    // Filter by difficulty
    if (filters?.difficulty) {
      paramCount++;
      query += ` AND tp.difficulty = $${paramCount}`;
      params.push(filters.difficulty);
    }

    // Filter by tags
    if (filters?.tags && filters.tags.length > 0) {
      paramCount++;
      query += ` AND tp.id IN (
        SELECT DISTINCT pt.problem_id
        FROM problem_tags pt
        JOIN tags tag ON pt.tag_id = tag.id
        WHERE tag.name = ANY($${paramCount}::text[])
      )`;
      params.push(filters.tags);
    }

    // Get total count
    const countQuery = `SELECT COUNT(*) as total FROM (${query}) as subquery`;
    const countResult = await db.query(countQuery, params);
    const total = parseInt(countResult.rows[0].total);

    // Add pagination
    query += ` ORDER BY tp.problem_number LIMIT $${paramCount + 1} OFFSET $${paramCount + 2}`;
    params.push(limit, offset);

    const result = await db.query(query, params);

    // Fetch tags for each problem
    const problems = await Promise.all(
      result.rows.map(async (problem) => {
        const tags = await this.getTagsForProblem(problem.id);
        return { ...problem, tags };
      })
    );

    return {
      data: problems,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit)
      }
    };
  }

  async getProblemById(problemId: string, includeRelated: boolean = true): Promise<Problem | null> {
    const result = await db.query(`
      SELECT
        tp.id,
        tp.test_id as "testId",
        t.name as "testName",
        tp.problem_number as "problemNumber",
        tp.title,
        tp.content,
        tp.difficulty,
        tp.points,
        tp.time_limit as "timeLimit",
        tp.images,
        tp.answer_choices_image as "answerChoicesImage",
        tp.correct_answer as "correctAnswer",
        tp.explanation
      FROM test_problems tp
      JOIN tests t ON tp.test_id = t.id
      WHERE tp.id = $1
    `, [problemId]);

    if (result.rows.length === 0) {
      return null;
    }

    const problem = result.rows[0];

    // Fetch tags, choices, and solutions
    const [tags, choices, solutions] = await Promise.all([
      this.getTagsForProblem(problemId),
      this.getChoicesForProblem(problemId),
      this.getSolutionsForProblem(problemId)
    ]);

    problem.tags = tags;
    problem.choices = choices;
    problem.solutions = solutions;

    if (includeRelated) {
      problem.relatedProblems = await this.getRelatedProblems(problemId);
    }

    return problem;
  }

  async searchProblems(filters: SearchFilters): Promise<PaginatedResult<Problem> & { facets?: SearchFacets }> {
    const page = filters.page || 1;
    const limit = filters.limit || 25;
    const offset = (page - 1) * limit;

    let query = `
      SELECT DISTINCT
        tp.id,
        tp.test_id as "testId",
        t.name as "testName",
        tp.problem_number as "problemNumber",
        tp.title,
        tp.content,
        tp.difficulty,
        tp.points,
        tp.time_limit as "timeLimit",
        tp.images,
        tp.answer_choices_image as "answerChoicesImage"
      FROM test_problems tp
      JOIN tests t ON tp.test_id = t.id
      WHERE 1=1
    `;

    const params: any[] = [];
    let paramCount = 0;

    // Full-text search
    if (filters.searchQuery) {
      paramCount++;
      query += ` AND tp.search_vector @@ plainto_tsquery('english', $${paramCount})`;
      params.push(filters.searchQuery);
    }

    // Filter by test category
    if (filters.testCategoryId) {
      paramCount++;
      query += ` AND t.category_id = $${paramCount}`;
      params.push(filters.testCategoryId);
    }

    // Filter by test
    if (filters.testId) {
      paramCount++;
      query += ` AND tp.test_id = $${paramCount}`;
      params.push(filters.testId);
    }

    // Filter by difficulty
    if (filters.difficulty) {
      paramCount++;
      query += ` AND tp.difficulty = $${paramCount}`;
      params.push(filters.difficulty);
    }

    // Filter by year
    if (filters.year) {
      paramCount++;
      query += ` AND t.year = $${paramCount}`;
      params.push(filters.year);
    }

    // Filter by tags
    if (filters.tags && filters.tags.length > 0) {
      paramCount++;
      query += ` AND tp.id IN (
        SELECT DISTINCT pt.problem_id
        FROM problem_tags pt
        JOIN tags tag ON pt.tag_id = tag.id
        WHERE tag.name = ANY($${paramCount}::text[])
      )`;
      params.push(filters.tags);
    }

    // Get total count
    const countQuery = `SELECT COUNT(*) as total FROM (${query}) as subquery`;
    const countResult = await db.query(countQuery, params);
    const total = parseInt(countResult.rows[0].total);

    // Add ordering and pagination
    if (filters.searchQuery) {
      query += `, ts_rank(tp.search_vector, plainto_tsquery('english', $1)) as rank ORDER BY rank DESC`;
    } else {
      query += ` ORDER BY t.year DESC, tp.problem_number`;
    }

    query += ` LIMIT $${paramCount + 1} OFFSET $${paramCount + 2}`;
    params.push(limit, offset);

    const result = await db.query(query, params);

    // Fetch tags for each problem
    const problems = await Promise.all(
      result.rows.map(async (problem) => {
        const tags = await this.getTagsForProblem(problem.id);
        return { ...problem, tags };
      })
    );

    return {
      data: problems,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit)
      }
    };
  }

  private async getTagsForProblem(problemId: string): Promise<Tag[]> {
    const result = await db.query(`
      SELECT
        t.id,
        t.name,
        t.category,
        t.description,
        t.color
      FROM tags t
      JOIN problem_tags pt ON t.id = pt.tag_id
      WHERE pt.problem_id = $1
      ORDER BY t.category, t.name
    `, [problemId]);

    return result.rows;
  }

  private async getChoicesForProblem(problemId: string): Promise<AnswerChoice[]> {
    const result = await db.query(`
      SELECT
        id,
        choice_label as "choiceLabel",
        choice_text as "choiceText",
        choice_order as "choiceOrder",
        is_correct as "isCorrect"
      FROM answer_choices
      WHERE problem_id = $1
      ORDER BY choice_order
    `, [problemId]);

    return result.rows;
  }

  private async getSolutionsForProblem(problemId: string): Promise<Solution[]> {
    const result = await db.query(`
      SELECT
        id,
        solution_text as "solutionText",
        solution_order as "solutionOrder",
        author,
        upvotes,
        is_official as "isOfficial"
      FROM problem_solutions
      WHERE problem_id = $1
      ORDER BY solution_order
    `, [problemId]);

    return result.rows;
  }

  private async getRelatedProblems(problemId: string): Promise<RelatedProblem[]> {
    const result = await db.query(`
      SELECT
        tp.id,
        tp.problem_number as "problemNumber",
        t.name as "testName",
        rp.relationship_type as "relationshipType"
      FROM related_problems rp
      JOIN test_problems tp ON rp.related_problem_id = tp.id
      JOIN tests t ON tp.test_id = t.id
      WHERE rp.problem_id = $1
      ORDER BY rp.relationship_type, tp.problem_number
    `, [problemId]);

    return result.rows;
  }
}
