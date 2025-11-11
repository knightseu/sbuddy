import { db } from '../models/database';
import { Problem } from './testViewerService';

export interface StudyPlan {
  id: string;
  userId: string;
  name: string;
  description?: string;
  isActive: boolean;
  targetTestDate?: Date;
  problemCount?: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface StudyPlanProblem {
  id: string;
  studyPlanId: string;
  problemId: string;
  addedAt: Date;
  completed: boolean;
  notes?: string;
  problem?: Problem;
}

export class StudyPlanService {
  // ============ Study Plans ============
  async getUserStudyPlans(userId: string): Promise<StudyPlan[]> {
    const result = await db.query(`
      SELECT
        sp.id,
        sp.user_id as "userId",
        sp.name,
        sp.description,
        sp.is_active as "isActive",
        sp.target_test_date as "targetTestDate",
        sp.created_at as "createdAt",
        sp.updated_at as "updatedAt",
        COUNT(spp.id) as "problemCount"
      FROM study_plans sp
      LEFT JOIN study_plan_problems spp ON sp.id = spp.study_plan_id
      WHERE sp.user_id = $1
      GROUP BY sp.id
      ORDER BY sp.is_active DESC, sp.updated_at DESC
    `, [userId]);

    return result.rows;
  }

  async getStudyPlanById(studyPlanId: string, userId: string): Promise<StudyPlan | null> {
    const result = await db.query(`
      SELECT
        sp.id,
        sp.user_id as "userId",
        sp.name,
        sp.description,
        sp.is_active as "isActive",
        sp.target_test_date as "targetTestDate",
        sp.created_at as "createdAt",
        sp.updated_at as "updatedAt",
        COUNT(spp.id) as "problemCount"
      FROM study_plans sp
      LEFT JOIN study_plan_problems spp ON sp.id = spp.study_plan_id
      WHERE sp.id = $1 AND sp.user_id = $2
      GROUP BY sp.id
    `, [studyPlanId, userId]);

    return result.rows[0] || null;
  }

  async getActiveStudyPlan(userId: string): Promise<StudyPlan | null> {
    const result = await db.query(`
      SELECT
        sp.id,
        sp.user_id as "userId",
        sp.name,
        sp.description,
        sp.is_active as "isActive",
        sp.target_test_date as "targetTestDate",
        sp.created_at as "createdAt",
        sp.updated_at as "updatedAt",
        COUNT(spp.id) as "problemCount"
      FROM study_plans sp
      LEFT JOIN study_plan_problems spp ON sp.id = spp.study_plan_id
      WHERE sp.user_id = $1 AND sp.is_active = true
      GROUP BY sp.id
      LIMIT 1
    `, [userId]);

    return result.rows[0] || null;
  }

  async createStudyPlan(
    userId: string,
    data: { name: string; description?: string; targetTestDate?: Date }
  ): Promise<StudyPlan> {
    const result = await db.query(`
      INSERT INTO study_plans (user_id, name, description, target_test_date, is_active)
      VALUES ($1, $2, $3, $4, false)
      RETURNING
        id,
        user_id as "userId",
        name,
        description,
        is_active as "isActive",
        target_test_date as "targetTestDate",
        created_at as "createdAt",
        updated_at as "updatedAt"
    `, [userId, data.name, data.description || null, data.targetTestDate || null]);

    return { ...result.rows[0], problemCount: 0 };
  }

  async updateStudyPlan(
    studyPlanId: string,
    userId: string,
    data: { name?: string; description?: string; isActive?: boolean; targetTestDate?: Date }
  ): Promise<StudyPlan | null> {
    const updates: string[] = [];
    const params: any[] = [studyPlanId, userId];
    let paramCount = 2;

    if (data.name !== undefined) {
      paramCount++;
      updates.push(`name = $${paramCount}`);
      params.push(data.name);
    }

    if (data.description !== undefined) {
      paramCount++;
      updates.push(`description = $${paramCount}`);
      params.push(data.description);
    }

    if (data.isActive !== undefined) {
      // If setting this plan to active, deactivate all other plans
      if (data.isActive) {
        await db.query(
          `UPDATE study_plans SET is_active = false WHERE user_id = $1 AND id != $2`,
          [userId, studyPlanId]
        );
      }

      paramCount++;
      updates.push(`is_active = $${paramCount}`);
      params.push(data.isActive);
    }

    if (data.targetTestDate !== undefined) {
      paramCount++;
      updates.push(`target_test_date = $${paramCount}`);
      params.push(data.targetTestDate);
    }

    if (updates.length === 0) {
      return this.getStudyPlanById(studyPlanId, userId);
    }

    updates.push(`updated_at = CURRENT_TIMESTAMP`);

    const query = `
      UPDATE study_plans
      SET ${updates.join(', ')}
      WHERE id = $1 AND user_id = $2
      RETURNING
        id,
        user_id as "userId",
        name,
        description,
        is_active as "isActive",
        target_test_date as "targetTestDate",
        created_at as "createdAt",
        updated_at as "updatedAt"
    `;

    const result = await db.query(query, params);

    if (result.rows.length === 0) {
      return null;
    }

    // Get problem count
    const countResult = await db.query(
      `SELECT COUNT(*) as count FROM study_plan_problems WHERE study_plan_id = $1`,
      [studyPlanId]
    );

    return {
      ...result.rows[0],
      problemCount: parseInt(countResult.rows[0].count)
    };
  }

  async deleteStudyPlan(studyPlanId: string, userId: string): Promise<boolean> {
    const result = await db.query(
      `DELETE FROM study_plans WHERE id = $1 AND user_id = $2 RETURNING id`,
      [studyPlanId, userId]
    );

    return result.rows.length > 0;
  }

  // ============ Study Plan Problems ============
  async getProblemsInPlan(
    studyPlanId: string,
    userId: string,
    filters?: { completed?: boolean; tags?: string[] }
  ): Promise<StudyPlanProblem[]> {
    let query = `
      SELECT
        spp.id,
        spp.study_plan_id as "studyPlanId",
        spp.problem_id as "problemId",
        spp.added_at as "addedAt",
        spp.completed,
        spp.notes,
        tp.problem_number as "problemNumber",
        tp.title,
        tp.content,
        tp.difficulty,
        tp.images,
        tp.answer_choices_image as "answerChoicesImage",
        t.name as "testName"
      FROM study_plan_problems spp
      JOIN test_problems tp ON spp.problem_id = tp.id
      JOIN tests t ON tp.test_id = t.id
      JOIN study_plans sp ON spp.study_plan_id = sp.id
      WHERE spp.study_plan_id = $1 AND sp.user_id = $2
    `;

    const params: any[] = [studyPlanId, userId];
    let paramCount = 2;

    if (filters?.completed !== undefined) {
      paramCount++;
      query += ` AND spp.completed = $${paramCount}`;
      params.push(filters.completed);
    }

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

    query += ` ORDER BY spp.added_at DESC`;

    const result = await db.query(query, params);

    return result.rows.map(row => ({
      id: row.id,
      studyPlanId: row.studyPlanId,
      problemId: row.problemId,
      addedAt: row.addedAt,
      completed: row.completed,
      notes: row.notes,
      problem: {
        id: row.problemId,
        testId: '',
        testName: row.testName,
        problemNumber: row.problemNumber,
        title: row.title,
        content: row.content,
        difficulty: row.difficulty,
        images: row.images,
        answerChoicesImage: row.answerChoicesImage
      }
    }));
  }

  async addProblemToPlan(studyPlanId: string, userId: string, problemId: string): Promise<StudyPlanProblem> {
    // Verify plan belongs to user
    const plan = await this.getStudyPlanById(studyPlanId, userId);
    if (!plan) {
      throw new Error('Study plan not found');
    }

    const result = await db.query(`
      INSERT INTO study_plan_problems (study_plan_id, problem_id, completed)
      VALUES ($1, $2, false)
      ON CONFLICT (study_plan_id, problem_id) DO NOTHING
      RETURNING
        id,
        study_plan_id as "studyPlanId",
        problem_id as "problemId",
        added_at as "addedAt",
        completed,
        notes
    `, [studyPlanId, problemId]);

    if (result.rows.length === 0) {
      // Problem already exists in plan, fetch it
      const existing = await db.query(`
        SELECT
          id,
          study_plan_id as "studyPlanId",
          problem_id as "problemId",
          added_at as "addedAt",
          completed,
          notes
        FROM study_plan_problems
        WHERE study_plan_id = $1 AND problem_id = $2
      `, [studyPlanId, problemId]);

      return existing.rows[0];
    }

    return result.rows[0];
  }

  async removeProblemFromPlan(studyPlanId: string, userId: string, problemId: string): Promise<boolean> {
    // Verify plan belongs to user
    const plan = await this.getStudyPlanById(studyPlanId, userId);
    if (!plan) {
      throw new Error('Study plan not found');
    }

    const result = await db.query(
      `DELETE FROM study_plan_problems
       WHERE study_plan_id = $1 AND problem_id = $2
       RETURNING id`,
      [studyPlanId, problemId]
    );

    return result.rows.length > 0;
  }

  async updateProblemInPlan(
    studyPlanId: string,
    userId: string,
    problemId: string,
    data: { completed?: boolean; notes?: string }
  ): Promise<StudyPlanProblem | null> {
    // Verify plan belongs to user
    const plan = await this.getStudyPlanById(studyPlanId, userId);
    if (!plan) {
      throw new Error('Study plan not found');
    }

    const updates: string[] = [];
    const params: any[] = [studyPlanId, problemId];
    let paramCount = 2;

    if (data.completed !== undefined) {
      paramCount++;
      updates.push(`completed = $${paramCount}`);
      params.push(data.completed);
    }

    if (data.notes !== undefined) {
      paramCount++;
      updates.push(`notes = $${paramCount}`);
      params.push(data.notes);
    }

    if (updates.length === 0) {
      return null;
    }

    const query = `
      UPDATE study_plan_problems
      SET ${updates.join(', ')}
      WHERE study_plan_id = $1 AND problem_id = $2
      RETURNING
        id,
        study_plan_id as "studyPlanId",
        problem_id as "problemId",
        added_at as "addedAt",
        completed,
        notes
    `;

    const result = await db.query(query, params);

    return result.rows[0] || null;
  }

  async isProblemInPlan(studyPlanId: string, userId: string, problemId: string): Promise<boolean> {
    const result = await db.query(`
      SELECT 1
      FROM study_plan_problems spp
      JOIN study_plans sp ON spp.study_plan_id = sp.id
      WHERE spp.study_plan_id = $1 AND spp.problem_id = $2 AND sp.user_id = $3
      LIMIT 1
    `, [studyPlanId, problemId, userId]);

    return result.rows.length > 0;
  }

  // ============ Statistics ============
  async getStudyPlanStats(studyPlanId: string, userId: string): Promise<any> {
    const result = await db.query(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN spp.completed THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN NOT spp.completed THEN 1 ELSE 0 END) as remaining,
        COUNT(DISTINCT tp.difficulty) as difficulties
      FROM study_plan_problems spp
      JOIN test_problems tp ON spp.problem_id = tp.id
      JOIN study_plans sp ON spp.study_plan_id = sp.id
      WHERE spp.study_plan_id = $1 AND sp.user_id = $2
    `, [studyPlanId, userId]);

    const difficultyResult = await db.query(`
      SELECT
        tp.difficulty,
        COUNT(*) as count
      FROM study_plan_problems spp
      JOIN test_problems tp ON spp.problem_id = tp.id
      JOIN study_plans sp ON spp.study_plan_id = sp.id
      WHERE spp.study_plan_id = $1 AND sp.user_id = $2
      GROUP BY tp.difficulty
    `, [studyPlanId, userId]);

    return {
      total: parseInt(result.rows[0].total) || 0,
      completed: parseInt(result.rows[0].completed) || 0,
      remaining: parseInt(result.rows[0].remaining) || 0,
      byDifficulty: difficultyResult.rows
    };
  }
}
