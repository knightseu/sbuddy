import { Request, Response } from 'express';
import { StudyPlanService } from '../services/studyPlanService';

const studyPlanService = new StudyPlanService();

export class StudyPlanController {
  // ============ Study Plans ============
  async getUserStudyPlans(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const plans = await studyPlanService.getUserStudyPlans(userId);
      res.json({ success: true, data: plans });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getStudyPlanById(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId } = req.params;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const plan = await studyPlanService.getStudyPlanById(planId, userId);

      if (!plan) {
        res.status(404).json({ success: false, error: 'Study plan not found' });
        return;
      }

      res.json({ success: true, data: plan });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getActiveStudyPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const plan = await studyPlanService.getActiveStudyPlan(userId);

      if (!plan) {
        res.status(404).json({ success: false, error: 'No active study plan found' });
        return;
      }

      res.json({ success: true, data: plan });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async createStudyPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { name, description, targetTestDate, isActive } = req.body;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      if (!name) {
        res.status(400).json({ success: false, error: 'Name is required' });
        return;
      }

      const plan = await studyPlanService.createStudyPlan(userId, {
        name,
        description,
        targetTestDate: targetTestDate ? new Date(targetTestDate) : undefined,
        isActive: isActive || false
      });

      res.status(201).json({ success: true, data: plan });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async updateStudyPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId } = req.params;
      const { name, description, isActive, targetTestDate } = req.body;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const updates: any = {};
      if (name !== undefined) updates.name = name;
      if (description !== undefined) updates.description = description;
      if (isActive !== undefined) updates.isActive = isActive;
      if (targetTestDate !== undefined) updates.targetTestDate = new Date(targetTestDate);

      const plan = await studyPlanService.updateStudyPlan(planId, userId, updates);

      if (!plan) {
        res.status(404).json({ success: false, error: 'Study plan not found' });
        return;
      }

      res.json({ success: true, data: plan });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async deleteStudyPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId } = req.params;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const deleted = await studyPlanService.deleteStudyPlan(planId, userId);

      if (!deleted) {
        res.status(404).json({ success: false, error: 'Study plan not found' });
        return;
      }

      res.json({ success: true, message: 'Study plan deleted' });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  // ============ Study Plan Problems ============
  async getProblemsInPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId } = req.params;
      const { completed, tags } = req.query;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const filters: any = {};
      if (completed !== undefined) filters.completed = completed === 'true';
      if (tags) filters.tags = Array.isArray(tags) ? tags : [tags];

      const problems = await studyPlanService.getProblemsInPlan(planId, userId, filters);
      res.json({ success: true, data: problems });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async addProblemToPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId, problemId } = req.params;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const result = await studyPlanService.addProblemToPlan(planId, userId, problemId);
      res.status(201).json({ success: true, data: result });
    } catch (error: any) {
      if (error.message === 'Study plan not found') {
        res.status(404).json({ success: false, error: error.message });
      } else {
        res.status(500).json({ success: false, error: error.message });
      }
    }
  }

  async removeProblemFromPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId, problemId } = req.params;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const removed = await studyPlanService.removeProblemFromPlan(planId, userId, problemId);

      if (!removed) {
        res.status(404).json({ success: false, error: 'Problem not found in plan' });
        return;
      }

      res.json({ success: true, message: 'Problem removed from plan' });
    } catch (error: any) {
      if (error.message === 'Study plan not found') {
        res.status(404).json({ success: false, error: error.message });
      } else {
        res.status(500).json({ success: false, error: error.message });
      }
    }
  }

  async updateProblemInPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId, problemId } = req.params;
      const { completed, notes } = req.body;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const updates: any = {};
      if (completed !== undefined) updates.completed = completed;
      if (notes !== undefined) updates.notes = notes;

      const result = await studyPlanService.updateProblemInPlan(planId, userId, problemId, updates);

      if (!result) {
        res.status(404).json({ success: false, error: 'Problem not found in plan' });
        return;
      }

      res.json({ success: true, data: result });
    } catch (error: any) {
      if (error.message === 'Study plan not found') {
        res.status(404).json({ success: false, error: error.message });
      } else {
        res.status(500).json({ success: false, error: error.message });
      }
    }
  }

  async checkProblemInPlan(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId, problemId } = req.params;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const inPlan = await studyPlanService.isProblemInPlan(planId, userId, problemId);
      res.json({ success: true, data: { inPlan } });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getStudyPlanStats(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).user?.userId;
      const { planId } = req.params;

      if (!userId) {
        res.status(401).json({ success: false, error: 'Unauthorized' });
        return;
      }

      const stats = await studyPlanService.getStudyPlanStats(planId, userId);
      res.json({ success: true, data: stats });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }
}
