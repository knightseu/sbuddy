# Generic Test Viewer System

## Overview

A scalable, generic test viewing platform that supports **any test type** (AMC, SAT, ACT, AP, GRE, etc.) with comprehensive tagging, filtering, and search capabilities.

## What We've Built

### ✅ Phase 1-3: Backend Infrastructure (COMPLETED)

#### 1. Database Schema (`src/models/database.ts`)
- **test_categories**: Test types (AMC, SAT, ACT, etc.)
- **tests**: Individual test instances (2024 AMC 10A, SAT Math June 2024, etc.)
- **tags**: Flexible tagging system with categories
- **test_problems**: Generic problem storage
- **problem_tags**: Many-to-many relationship for tags
- **answer_choices**: Multiple choice options
- **problem_solutions**: Multiple solutions per problem
- **related_problems**: Problem relationships
- **study_plans**: User study plans
- **study_plan_problems**: Problems in study plans
- **Full-text search** with PostgreSQL tsvector

#### 2. Data Migration Script (`src/scripts/importTestData.ts`)
- Generic importer interface
- AMC test importer with auto-tagging
- Automatic subject detection (algebra, geometry, etc.)
- Tag extraction from problem content
- Extensible for other test types

#### 3. Service Layer
- **TestViewerService** (`src/services/testViewerService.ts`):
  - Test category management
  - Test and problem retrieval
  - Tag filtering
  - Full-text search
  - Pagination
- **StudyPlanService** (`src/services/studyPlanService.ts`):
  - User study plan management
  - Problem tracking
  - Progress statistics

#### 4. API Endpoints (`src/routes/testViewer.ts`)
All endpoints accessible under `/api/v1/viewer/`

**Public Endpoints:**
```
GET  /test-categories                     # List all test categories
GET  /test-categories/:categoryId         # Get category details
GET  /test-categories/:categoryId/tests   # Get tests in category
GET  /tests/:testId                       # Get test details
GET  /tests/:testId/problems               # Get problems in test (with filtering)
GET  /tags                                # Get all tags
GET  /problems/search                     # Search problems
GET  /problems/:problemId                 # Get problem details
```

**Protected Endpoints (require authentication):**
```
GET    /study-plans                       # Get user's study plans
POST   /study-plans                       # Create study plan
PUT    /study-plans/:planId               # Update study plan
DELETE /study-plans/:planId               # Delete study plan
GET    /study-plans/:planId/problems      # Get problems in plan
POST   /study-plans/:planId/problems/:problemId    # Add problem to plan
DELETE /study-plans/:planId/problems/:problemId    # Remove from plan
GET    /study-plans/:planId/stats         # Get plan statistics
```

## How to Use

### Step 1: Setup Database

The database tables will be automatically created when you start the server:

```bash
npm run dev
```

### Step 2: Import Test Data

Import your AMC test data from JSON files:

```bash
npm run import:tests:data
```

This will:
- Read all tests from `crawled_data/`
- Create test categories
- Import problems with auto-tagging
- Extract subjects (algebra, geometry, etc.)
- Create answer choices and solutions

### Step 3: Verify Import

Check the import results:
```bash
curl http://localhost:3000/api/v1/viewer/test-categories
```

You should see:
```json
{
  "success": true,
  "data": [
    {
      "id": "...",
      "name": "amc",
      "displayName": "American Mathematics Competition",
      "testCount": 34,
      "problemCount": 850
    }
  ]
}
```

### Step 4: Test API Endpoints

**Get all AMC tests:**
```bash
curl http://localhost:3000/api/v1/viewer/test-categories/{categoryId}/tests
```

**Get problems from a specific test:**
```bash
curl http://localhost:3000/api/v1/viewer/tests/{testId}/problems
```

**Filter problems by tags:**
```bash
curl "http://localhost:3000/api/v1/viewer/tests/{testId}/problems?tags=algebra,medium"
```

**Search problems:**
```bash
curl "http://localhost:3000/api/v1/viewer/problems/search?q=quadratic&difficulty=medium"
```

**Get all tags:**
```bash
curl http://localhost:3000/api/v1/viewer/tags
```

## Tag System

### Tag Categories

1. **difficulty**: `easy`, `medium`, `hard`
2. **subject**: `algebra`, `geometry`, `probability`, `number-theory`, `combinatorics`
3. **topic**: Specific topics from problem metadata
4. **year**: `year-2024`, `year-2023`, etc.
5. **test-variant**: `amc-10a`, `amc-10b`, etc.

### Auto-Detection

The system automatically detects subjects based on keywords:
- **Algebra**: equation, variable, solve, polynomial, quadratic, linear
- **Geometry**: triangle, circle, angle, area, perimeter, radius
- **Probability**: probability, chance, random, expected, coin, dice
- **Number Theory**: prime, divisible, factor, multiple, remainder
- **Combinatorics**: combination, permutation, arrange, ways to, select

## Example API Calls

### Get All Tests
```bash
curl http://localhost:3000/api/v1/viewer/test-categories
```

### Get Specific Test Problems
```bash
curl http://localhost:3000/api/v1/viewer/tests/{testId}/problems?page=1&limit=25
```

### Search with Multiple Filters
```bash
curl "http://localhost:3000/api/v1/viewer/problems/search?q=triangle&tags=geometry,medium&year=2024"
```

### Create Study Plan (requires auth)
```bash
curl -X POST http://localhost:3000/api/v1/viewer/study-plans \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "AMC 10 Practice", "description": "Preparing for AMC 10"}'
```

### Add Problem to Study Plan (requires auth)
```bash
curl -X POST http://localhost:3000/api/v1/viewer/study-plans/{planId}/problems/{problemId} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Next Steps

### Phase 4: Frontend Updates (TODO)

The frontend needs to be updated to use the new API instead of local files:

1. **Create API Client** (`public/viewer/apiClient.js`)
2. **Update `index.html`** - Use API for test list
3. **Update `problem.html`** - Use API for problem details
4. **Update `studyPlan.html`** - Use API for study plans
5. **Add Tag Filtering UI** - Interactive tag selection
6. **Add Search Bar** - Full-text problem search
7. **Authentication Flow** - Login/signup for study plans

### Phase 5: Testing (TODO)

1. Import test data
2. Verify all API endpoints
3. Test tag filtering
4. Test search functionality
5. Test study plan features

## Adding New Test Types

To add SAT, ACT, or other test types:

1. **Create a new importer class** in `src/scripts/importTestData.ts`:
```typescript
class SatTestImporter implements TestImporter {
  async importTest(filePath: string) {
    // SAT-specific import logic
  }
}
```

2. **Register the importer**:
```typescript
const importers: Record<string, TestImporter> = {
  'amc': new AmcTestImporter(),
  'sat': new SatTestImporter(),
  'act': new ActTestImporter(),
};
```

3. **Run the import**:
```bash
npm run import:tests -- sat sat_data_directory
```

## Database Queries

### Get problems by multiple tags
```sql
SELECT p.*
FROM test_problems p
JOIN problem_tags pt ON p.id = pt.problem_id
JOIN tags t ON pt.tag_id = t.id
WHERE t.name IN ('algebra', 'medium')
GROUP BY p.id
HAVING COUNT(DISTINCT t.name) = 2;
```

### Full-text search
```sql
SELECT p.*, ts_rank(p.search_vector, query) AS rank
FROM test_problems p,
     plainto_tsquery('english', 'quadratic equation') query
WHERE p.search_vector @@ query
ORDER BY rank DESC;
```

## Features

✅ Generic, scalable schema for all test types
✅ Comprehensive tagging system
✅ Full-text search with PostgreSQL
✅ Tag-based filtering
✅ Pagination support
✅ User study plans
✅ Problem progress tracking
✅ Auto-tagging based on content
✅ Related problems
✅ Multiple solutions per problem
✅ RESTful API

## Architecture Benefits

1. **Scalable**: Supports unlimited test types
2. **Flexible**: JSONB metadata for test-specific data
3. **Searchable**: Full-text search with ranking
4. **Tagged**: Multi-dimensional filtering
5. **Fast**: Optimized indexes
6. **User-friendly**: Study plan management
7. **Extensible**: Easy to add new test types

## File Structure

```
src/
├── models/
│   └── database.ts              # Database schema
├── scripts/
│   └── importTestData.ts        # Migration script
├── services/
│   ├── testViewerService.ts     # Test viewer logic
│   └── studyPlanService.ts      # Study plan logic
├── controllers/
│   ├── testViewerController.ts  # API handlers
│   └── studyPlanController.ts   # Study plan handlers
└── routes/
    ├── testViewer.ts            # API routes
    └── index.ts                 # Main router
```

## Performance Considerations

- **Indexes**: All foreign keys and search fields indexed
- **Pagination**: Default 25 items per page
- **Search Vector**: Auto-updated via trigger
- **Tag Caching**: Tag manager caches frequently used tags
- **Connection Pooling**: PostgreSQL pool for scalability

## Security

- **Public endpoints**: Test data viewable by all
- **Protected endpoints**: Study plans require JWT auth
- **SQL injection**: Parameterized queries
- **Rate limiting**: Can be added to search endpoints
- **CORS**: Configure as needed

## Support

For issues or questions:
1. Check API response errors
2. Verify database connection
3. Check import logs
4. Review tag extraction logic
5. Test with Postman/curl

---

**Status**: Backend complete ✅ | Frontend TODO ⏳ | Testing TODO ⏳
