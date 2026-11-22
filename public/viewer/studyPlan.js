/**
 * Study Plan Management - API-backed version
 * Handles creating, updating, and managing study plans using the database API
 */

class StudyPlanManager {
    constructor() {
        this.apiBase = '/api/v1/viewer';
        this.guestIdKey = 'sbuddy_guest_id';
        this.oldStorageKey = 'amc_study_plans'; // For migration
        this.oldActiveKey = 'amc_active_plan'; // For migration
        this.guestId = null;
        this.activePlan = null;
        this.plans = [];
        this.initialized = false;
        this.cache = new Map(); // Cache for plans
    }

    // Initialize the manager and migrate old data if needed
    // Concurrent callers share one in-flight initialization promise.
    initialize() {
        if (!this.initPromise) {
            this.initPromise = this.doInitialize();
        }
        return this.initPromise;
    }

    async doInitialize() {
        // Get or create guest ID
        this.guestId = localStorage.getItem(this.guestIdKey);
        if (!this.guestId) {
            this.guestId = `guest_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            localStorage.setItem(this.guestIdKey, this.guestId);
        }

        // Check for old localStorage data and migrate
        await this.migrateOldData();

        // Load plans from API
        await this.loadPlans();

        this.initialized = true;
    }

    // Get headers for API calls
    getHeaders() {
        return {
            'Content-Type': 'application/json',
            'X-Guest-ID': this.guestId
        };
    }

    // Migrate old localStorage data to API
    async migrateOldData() {
        const oldPlans = localStorage.getItem(this.oldStorageKey);
        if (!oldPlans) return;

        try {
            const plans = JSON.parse(oldPlans);
            const oldActivePlanId = localStorage.getItem(this.oldActiveKey);

            // Create plans in API
            for (const [planId, planData] of Object.entries(plans)) {
                const isActive = planId === oldActivePlanId;

                // Create the plan
                const response = await fetch(`${this.apiBase}/study-plans`, {
                    method: 'POST',
                    headers: this.getHeaders(),
                    body: JSON.stringify({
                        name: planData.name || 'Migrated Plan',
                        description: 'Migrated from localStorage'
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    const newPlanId = result.data.id;

                    // Set as active if it was active before
                    if (isActive) {
                        await fetch(`${this.apiBase}/study-plans/${newPlanId}`, {
                            method: 'PUT',
                            headers: this.getHeaders(),
                            body: JSON.stringify({ isActive: true })
                        });
                    }

                    // Add problems to the plan
                    if (planData.problems && planData.problems.length > 0) {
                        for (const problem of planData.problems) {
                            // Problem might be in old format, only migrate if it has an ID
                            if (problem.id) {
                                try {
                                    await fetch(`${this.apiBase}/study-plans/${newPlanId}/problems/${problem.id}`, {
                                        method: 'POST',
                                        headers: this.getHeaders()
                                    });
                                } catch (err) {
                                    console.warn('Failed to migrate problem:', problem, err);
                                }
                            }
                        }
                    }
                }
            }

            // Clear old data
            localStorage.removeItem(this.oldStorageKey);
            localStorage.removeItem(this.oldActiveKey);
            console.log('Successfully migrated study plans from localStorage to database');
        } catch (error) {
            console.error('Error migrating old data:', error);
        }
    }

    // Load all plans from API
    // Must not call initialize() (directly or via public methods): it runs
    // during initialization, and re-entering initialize() loops forever.
    async loadPlans() {
        try {
            await this.fetchPlans();

            // Ensure there is an active plan, then refresh once
            if (!this.activePlan) {
                if (this.plans.length === 0) {
                    await this.requestCreatePlan('My Study Plan', true);
                } else {
                    await this.requestSetActivePlan(this.plans[0].id);
                }
                await this.fetchPlans();
            }
        } catch (error) {
            console.error('Error loading plans:', error);
            // Fallback to empty state
            this.plans = [];
            this.activePlan = null;
        }
    }

    async fetchPlans() {
        const response = await fetch(`${this.apiBase}/study-plans`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error(`Failed to load plans: ${response.status}`);
        const result = await response.json();
        this.plans = result.data || [];
        this.activePlan = this.plans.find(p => p.isActive) || null;
    }

    // Returns the new plan's id, or null on failure
    async requestCreatePlan(name, setAsActive) {
        const response = await fetch(`${this.apiBase}/study-plans`, {
            method: 'POST',
            headers: this.getHeaders(),
            body: JSON.stringify({
                name: name || 'New Study Plan',
                isActive: setAsActive
            })
        });
        if (!response.ok) return null;
        const result = await response.json();
        return result.data.id;
    }

    async requestSetActivePlan(planId) {
        const response = await fetch(`${this.apiBase}/study-plans/${planId}`, {
            method: 'PUT',
            headers: this.getHeaders(),
            body: JSON.stringify({ isActive: true })
        });
        return response.ok;
    }

    // Get all study plans
    async getPlans() {
        await this.initialize();
        return this.plans;
    }

    // Get active plan ID
    getActivePlanId() {
        return this.activePlan?.id || null;
    }

    // Set active plan
    async setActivePlan(planId) {
        await this.initialize();

        try {
            if (await this.requestSetActivePlan(planId)) {
                await this.loadPlans(); // Reload to update state
                return true;
            }
        } catch (error) {
            console.error('Error setting active plan:', error);
        }
        return false;
    }

    // Get active plan
    async getActivePlan() {
        await this.initialize();
        return this.activePlan;
    }

    // Create new plan
    async createPlan(name, setAsActive = false) {
        await this.initialize();

        try {
            const id = await this.requestCreatePlan(name, setAsActive);
            if (id) {
                await this.loadPlans(); // Reload to update state
                return id;
            }
        } catch (error) {
            console.error('Error creating plan:', error);
        }
        return null;
    }

    // Delete plan
    async deletePlan(planId) {
        await this.initialize();

        try {
            const response = await fetch(`${this.apiBase}/study-plans/${planId}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });

            if (response.ok) {
                await this.loadPlans(); // Reload to update state
                return true;
            }
        } catch (error) {
            console.error('Error deleting plan:', error);
        }
        return false;
    }

    // Rename plan
    async renamePlan(planId, newName) {
        await this.initialize();

        try {
            const response = await fetch(`${this.apiBase}/study-plans/${planId}`, {
                method: 'PUT',
                headers: this.getHeaders(),
                body: JSON.stringify({ name: newName })
            });

            if (response.ok) {
                await this.loadPlans(); // Reload to update state
                return true;
            }
        } catch (error) {
            console.error('Error renaming plan:', error);
        }
        return false;
    }

    // Check if problem is in active plan by ID
    async isProblemInPlanById(problemId) {
        await this.initialize();

        if (!this.activePlan) return false;

        try {
            const response = await fetch(
                `${this.apiBase}/study-plans/${this.activePlan.id}/problems/${problemId}/check`,
                { headers: this.getHeaders() }
            );

            if (response.ok) {
                const result = await response.json();
                return result.data.inPlan;
            }
        } catch (error) {
            console.error('Error checking problem in plan:', error);
        }
        return false;
    }

    // Add problem by ID (with full problem data)
    async addProblemById(problemId, problemData = {}) {
        await this.initialize();

        if (!this.activePlan) {
            await this.createPlan('My Study Plan', true);
            await this.initialize();
        }

        try {
            const response = await fetch(
                `${this.apiBase}/study-plans/${this.activePlan.id}/problems/${problemId}`,
                {
                    method: 'POST',
                    headers: this.getHeaders()
                }
            );

            if (response.ok) {
                // Update plan count
                await this.loadPlans();
                return true;
            }
        } catch (error) {
            console.error('Error adding problem to plan:', error);
        }
        return false;
    }

    // Remove problem by ID
    async removeProblemById(problemId) {
        await this.initialize();

        if (!this.activePlan) return false;

        try {
            const response = await fetch(
                `${this.apiBase}/study-plans/${this.activePlan.id}/problems/${problemId}`,
                {
                    method: 'DELETE',
                    headers: this.getHeaders()
                }
            );

            if (response.ok) {
                // Update plan count
                await this.loadPlans();
                return true;
            }
        } catch (error) {
            console.error('Error removing problem from plan:', error);
        }
        return false;
    }

    // Toggle problem by ID
    async toggleProblemById(problemId) {
        const inPlan = await this.isProblemInPlanById(problemId);

        if (inPlan) {
            await this.removeProblemById(problemId);
            return false;
        } else {
            const problemData = window.allProblems?.find(p => p.id === problemId) || {};
            await this.addProblemById(problemId, problemData);
            return true;
        }
    }

    // Get problem count for active plan
    async getProblemCount() {
        await this.initialize();
        return this.activePlan?.problemCount || 0;
    }

    // Get all problems in active plan
    async getProblemsInPlan() {
        await this.initialize();

        if (!this.activePlan) return [];

        try {
            const response = await fetch(
                `${this.apiBase}/study-plans/${this.activePlan.id}/problems`,
                { headers: this.getHeaders() }
            );

            if (response.ok) {
                const result = await response.json();
                return result.data || [];
            }
        } catch (error) {
            console.error('Error getting problems in plan:', error);
        }
        return [];
    }

    // Legacy methods for backward compatibility (deprecated, use ID-based methods)

    isProblemInPlan(problemNumber, testFile = null) {
        console.warn('isProblemInPlan is deprecated, use isProblemInPlanById');
        return false;
    }

    addProblem(problemNumber, testFile = 'amc_2012_10a_problems.json') {
        console.warn('addProblem is deprecated, use addProblemById');
        return false;
    }

    removeProblem(problemNumber, testFile = null) {
        console.warn('removeProblem is deprecated, use removeProblemById');
        return false;
    }

    toggleProblem(problemNumber, testFile = 'amc_2012_10a_problems.json') {
        console.warn('toggleProblem is deprecated, use toggleProblemById');
        return false;
    }

    savePlans(plans) {
        console.warn('savePlans is deprecated, changes are saved via API');
    }
}

// Create global instance
window.studyPlanManager = new StudyPlanManager();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.studyPlanManager.initialize();
    });
} else {
    window.studyPlanManager.initialize();
}
