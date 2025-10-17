const MockData = {
    isActive: typeof GetParentResourceName === 'undefined',
    currentScenarioKey: 'police_department',
    scenarios: {
        police_department: {
            label: 'Police Department',
            business: {
                jobLabel: 'Police Department',
                jobName: 'police',
                name: 'Los Santos Police Department',
                funds: 45230,
                owner: 'ABC12345',
                user: {
                    name: 'John Doe',
                    role: 'boss'
                },
                employees: [
                    { id: 1, name: 'Jane Smith', citizenid: 'DEF67890', grade: 2, wage: 45 },
                    { id: 2, name: 'Bob Johnson', citizenid: 'GHI01234', grade: 1, wage: 35 },
                    { id: 3, name: 'Alice Brown', citizenid: 'JKL56789', grade: 3, wage: 55 },
                    { id: 4, name: 'Carlos Ortega', citizenid: 'MNO13579', grade: 4, wage: 75 },
                    { id: 5, name: 'Sofia Navarro', citizenid: 'PQR24680', grade: 1, wage: 35 }
                ]
            }
        },
        ambulance: {
            label: 'Ambulance Service',
            business: {
                jobLabel: 'Ambulance Service',
                jobName: 'ambulance',
                name: 'Central Medical Services',
                funds: 78560,
                owner: 'XYZ90210',
                user: {
                    name: 'Emily Clark',
                    role: 'boss'
                },
                employees: [
                    { id: 11, name: 'Liam Johnson', citizenid: 'EMS00123', grade: 3, wage: 62 },
                    { id: 12, name: 'Ava Martinez', citizenid: 'EMS00456', grade: 2, wage: 48 },
                    { id: 13, name: 'Noah Williams', citizenid: 'EMS00789', grade: 1, wage: 35 },
                    { id: 14, name: 'Olivia Brown', citizenid: 'EMS00999', grade: 4, wage: 75 }
                ]
            }
        },
        taxi: {
            label: 'Taxi Company',
            business: {
                jobLabel: 'Downtown Cab Co.',
                jobName: 'taxi',
                name: 'Downtown Cab Co.',
                funds: 18240,
                owner: 'CAB33445',
                user: {
                    name: 'Miguel Torres',
                    role: 'employee'
                },
                employees: [
                    { id: 21, name: 'Gabriela Cruz', citizenid: 'CAB00111', grade: 2, wage: 32 },
                    { id: 22, name: 'Hector Alvarez', citizenid: 'CAB00222', grade: 1, wage: 28 },
                    { id: 23, name: 'Valentina Rios', citizenid: 'CAB00333', grade: 3, wage: 36 }
                ]
            }
        }
    },

    applyScenario(key) {
        if (!this.isActive) {
            return null;
        }

        const scenario = this.scenarios[key];
        if (!scenario) {
            console.warn(`[MockData] Scenario "${key}" not found.`);
            return null;
        }

        this.currentScenarioKey = key;
        const businessClone = JSON.parse(JSON.stringify(scenario.business));
        BusinessAPI.currentBusiness = businessClone;

        if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.applyBusinessData === 'function') {
            BusinessManager.applyBusinessData(businessClone);
        }

        return businessClone;
    },

    getBusiness() {
        if (!this.isActive) {
            return null;
        }

        if (!BusinessAPI.currentBusiness || !BusinessAPI.currentBusiness.name) {
            return this.applyScenario(this.currentScenarioKey);
        }

        return JSON.parse(JSON.stringify(BusinessAPI.currentBusiness));
    },

    init() {
        if (!this.isActive) {
            return;
        }

        this.applyScenario(this.currentScenarioKey);
        this.injectDevToolbar();
        this.setupKeyboardShortcuts();

        console.info('%cMock data mode enabled for Business Manager UI', 'color: #38bdf8; font-weight: bold;');
        console.info('Use the floating toolbar or press Ctrl+Alt+M to toggle the panel.');
    },

    injectDevToolbar() {
        if (this.toolbar || typeof $ === 'undefined') {
            return;
        }

        const options = Object.entries(this.scenarios)
            .map(([key, scenario]) => `<option value="${key}" ${key === this.currentScenarioKey ? 'selected' : ''}>${scenario.label}</option>`)
            .join('');

        const toolbar = $(`
            <div class="mock-data-toolbar" style="
                position: fixed;
                bottom: 1.5rem;
                right: 1.5rem;
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid rgba(148, 163, 184, 0.4);
                border-radius: 12px;
                padding: 1rem;
                display: flex;
                flex-direction: column;
                gap: 0.75rem;
                color: #e2e8f0;
                font-family: 'Inter', sans-serif;
                z-index: 9999;
                width: 220px;
                box-shadow: 0 10px 25px rgba(15, 23, 42, 0.35);
            ">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <strong style="font-size: 0.95rem;">Mock Scenario</strong>
                    <button type="button" class="mock-close" style="
                        background: transparent;
                        border: none;
                        color: #94a3b8;
                        cursor: pointer;
                        font-size: 0.9rem;
                    ">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <label style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8;">
                    Scenario
                    <select class="mock-scenario-select" style="
                        background: rgba(30, 41, 59, 0.9);
                        border: 1px solid rgba(148, 163, 184, 0.3);
                        border-radius: 8px;
                        padding: 0.5rem;
                        color: #e2e8f0;
                        font-size: 0.9rem;
                    ">
                        ${options}
                    </select>
                </label>
                <button type="button" class="mock-toggle" style="
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.5rem;
                    background: linear-gradient(135deg, #6366f1, #22d3ee);
                    border: none;
                    border-radius: 8px;
                    padding: 0.6rem 0.75rem;
                    color: #0f172a;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s ease;
                ">
                    <i class="fas fa-desktop"></i>
                    <span>Toggle Panel</span>
                </button>
            </div>
        `);

        toolbar.find('.mock-close').on('click', () => {
            toolbar.toggleClass('collapsed');
            const isCollapsed = toolbar.hasClass('collapsed');
            toolbar.css('transform', isCollapsed ? 'translateY(calc(100% - 2.5rem))' : 'translateY(0)');
        });

        toolbar.find('.mock-scenario-select').on('change', (event) => {
            this.applyScenario(event.target.value);
        });

        toolbar.find('.mock-toggle').on('click', () => {
            if (typeof window.togglePanel === 'function') {
                window.togglePanel();
            } else if (typeof BusinessManager !== 'undefined') {
                if (BusinessManager.isOpen) {
                    BusinessManager.hidePanel();
                } else {
                    BusinessManager.showPanel();
                }
            }
        });

        $('body').append(toolbar);
        this.toolbar = toolbar;
    },

    setupKeyboardShortcuts() {
        if (typeof window === 'undefined') {
            return;
        }

        window.addEventListener('keydown', (event) => {
            if (!event.ctrlKey || !event.altKey || event.key.toLowerCase() !== 'm') {
                return;
            }

            event.preventDefault();

            if (typeof window.togglePanel === 'function') {
                window.togglePanel();
            }
        });
    }
};

window.MockData = MockData;

if (MockData.isActive) {
    MockData.applyScenario(MockData.currentScenarioKey);
}

$(document).ready(() => {
    MockData.init();
});
