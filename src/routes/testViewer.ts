import express from 'express';
import { TestViewerController } from '../controllers/testViewerController';
import { StudyPlanController } from '../controllers/studyPlanController';
import { authenticateToken, optionalAuth } from '../middleware/auth';

const router = express.Router();
const testViewerController = new TestViewerController();
const studyPlanController = new StudyPlanController();

// ============ Public Routes (Test Viewer) ============

// Test Categories
router.get('/test-categories', testViewerController.getAllCategories.bind(testViewerController));
router.get('/test-categories/:categoryId', testViewerController.getCategoryById.bind(testViewerController));

// Tests
router.get('/test-categories/:categoryId/tests', testViewerController.getTestsByCategory.bind(testViewerController));
router.get('/tests/:testId', testViewerController.getTestById.bind(testViewerController));

// Tags
router.get('/tags', testViewerController.getAllTags.bind(testViewerController));

// Problems
router.get('/tests/:testId/problems', testViewerController.getProblemsByTest.bind(testViewerController));
router.get('/problems/search', testViewerController.searchProblems.bind(testViewerController));
router.get('/problems/:problemId', testViewerController.getProblemById.bind(testViewerController));

// ============ Study Plans (supports both authenticated users and guests) ============

// Study Plans
router.get('/study-plans', optionalAuth, studyPlanController.getUserStudyPlans.bind(studyPlanController));
router.get('/study-plans/active', optionalAuth, studyPlanController.getActiveStudyPlan.bind(studyPlanController));
router.get('/study-plans/:planId', optionalAuth, studyPlanController.getStudyPlanById.bind(studyPlanController));
router.post('/study-plans', optionalAuth, studyPlanController.createStudyPlan.bind(studyPlanController));
router.put('/study-plans/:planId', optionalAuth, studyPlanController.updateStudyPlan.bind(studyPlanController));
router.delete('/study-plans/:planId', optionalAuth, studyPlanController.deleteStudyPlan.bind(studyPlanController));

// Study Plan Problems
router.get('/study-plans/:planId/problems', optionalAuth, studyPlanController.getProblemsInPlan.bind(studyPlanController));
router.post('/study-plans/:planId/problems/:problemId', optionalAuth, studyPlanController.addProblemToPlan.bind(studyPlanController));
router.delete('/study-plans/:planId/problems/:problemId', optionalAuth, studyPlanController.removeProblemFromPlan.bind(studyPlanController));
router.put('/study-plans/:planId/problems/:problemId', optionalAuth, studyPlanController.updateProblemInPlan.bind(studyPlanController));
router.get('/study-plans/:planId/problems/:problemId/check', optionalAuth, studyPlanController.checkProblemInPlan.bind(studyPlanController));

// Study Plan Statistics
router.get('/study-plans/:planId/stats', optionalAuth, studyPlanController.getStudyPlanStats.bind(studyPlanController));

export default router;
