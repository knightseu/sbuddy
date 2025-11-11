import { Request, Response } from 'express';
import { TestViewerService } from '../services/testViewerService';

const testViewerService = new TestViewerService();

export class TestViewerController {
  // ============ Test Categories ============
  async getAllCategories(req: Request, res: Response): Promise<void> {
    try {
      const categories = await testViewerService.getAllCategories();
      res.json({ success: true, data: categories });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getCategoryById(req: Request, res: Response): Promise<void> {
    try {
      const { categoryId } = req.params;
      const category = await testViewerService.getCategoryById(categoryId);

      if (!category) {
        res.status(404).json({ success: false, error: 'Category not found' });
        return;
      }

      res.json({ success: true, data: category });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  // ============ Tests ============
  async getTestsByCategory(req: Request, res: Response): Promise<void> {
    try {
      const { categoryId } = req.params;
      const { year, variant } = req.query;

      const filters: any = {};
      if (year) filters.year = parseInt(year as string);
      if (variant) filters.variant = variant as string;

      const tests = await testViewerService.getTestsByCategory(categoryId, filters);
      res.json({ success: true, data: tests });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getTestById(req: Request, res: Response): Promise<void> {
    try {
      const { testId } = req.params;
      const test = await testViewerService.getTestById(testId);

      if (!test) {
        res.status(404).json({ success: false, error: 'Test not found' });
        return;
      }

      res.json({ success: true, data: test });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  // ============ Tags ============
  async getAllTags(req: Request, res: Response): Promise<void> {
    try {
      const { category, search } = req.query;

      const filters: any = {};
      if (category) filters.category = category as string;
      if (search) filters.search = search as string;

      const tags = await testViewerService.getAllTags(filters);
      res.json({ success: true, data: tags });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  // ============ Problems ============
  async getProblemsByTest(req: Request, res: Response): Promise<void> {
    try {
      const { testId } = req.params;
      const { tags, difficulty, page, limit } = req.query;

      const filters: any = {
        page: page ? parseInt(page as string) : 1,
        limit: limit ? parseInt(limit as string) : 25
      };

      if (tags) {
        filters.tags = Array.isArray(tags) ? tags : [tags];
      }
      if (difficulty) {
        filters.difficulty = difficulty as string;
      }

      const result = await testViewerService.getProblemsByTest(testId, filters);
      res.json({ success: true, ...result });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getProblemById(req: Request, res: Response): Promise<void> {
    try {
      const { problemId } = req.params;
      const { includeRelated } = req.query;

      const problem = await testViewerService.getProblemById(
        problemId,
        includeRelated !== 'false'
      );

      if (!problem) {
        res.status(404).json({ success: false, error: 'Problem not found' });
        return;
      }

      res.json({ success: true, data: problem });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async searchProblems(req: Request, res: Response): Promise<void> {
    try {
      const {
        q,
        tags,
        difficulty,
        testCategoryId,
        testId,
        year,
        page,
        limit
      } = req.query;

      const filters: any = {
        page: page ? parseInt(page as string) : 1,
        limit: limit ? parseInt(limit as string) : 25
      };

      if (q) filters.searchQuery = q as string;
      if (tags) filters.tags = Array.isArray(tags) ? tags : [tags];
      if (difficulty) filters.difficulty = difficulty as string;
      if (testCategoryId) filters.testCategoryId = testCategoryId as string;
      if (testId) filters.testId = testId as string;
      if (year) filters.year = parseInt(year as string);

      const result = await testViewerService.searchProblems(filters);
      res.json({ success: true, ...result });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }
}
