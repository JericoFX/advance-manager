$(document).ready(function() {
    // Inicializar la aplicación
    BusinessManager.init();
});

const BusinessManager = {
    isOpen: false,
    
    init() {
        this.bindEvents();

        const shouldAutoOpen = typeof FiveMCallbacks === 'undefined' || !FiveMCallbacks.isFiveM;

        if (shouldAutoOpen) {
            this.showPanel(); // Para testing en navegador
        }
    },
    
    bindEvents() {
        // Cerrar panel
        $('#closeBtn').on('click', () => {
            this.hidePanel();
        });
        
        // Overlay click para cerrar
        $('#overlay').on('click', () => {
            this.hidePanel();
        });
        
        // Botones principales
        $('#depositBtn').on('click', () => {
            this.showDepositModal();
        });
        
        $('#withdrawBtn').on('click', () => {
            this.showWithdrawModal();
        });
        
        $('#hireBtn').on('click', () => {
            this.showHireModal();
        });
        
        $('#manageBtn').on('click', () => {
            this.showEmployeesList();
        });
        
        // Modal events
        $('#modalClose, #modalCancel').on('click', () => {
            this.hideModal();
        });
        
        $('#modalConfirm').on('click', () => {
            this.handleModalConfirm();
        });
        
        // Escape key para cerrar modales
        $(document).on('keydown', (e) => {
            if (e.key === 'Escape') {
                if ($('#modal').hasClass('active')) {
                    this.hideModal();
                } else if (this.isOpen) {
                    this.hidePanel();
                }
            }
        });
    },
    
    showPanel() {
        this.isOpen = true;
        $('#overlay').addClass('active');
        $('#businessPanel').addClass('active');

        if (typeof FiveMCallbacks !== 'undefined' && FiveMCallbacks.isFiveM) {
            if (typeof this.loadBusinessData === 'function') {
                this.loadBusinessData();
            }
            return;
        }

        // Simular datos para testing
        this.loadMockData();
    },
    
    hidePanel() {
        this.isOpen = false;
        $('#overlay').removeClass('active');
        $('#businessPanel').removeClass('active');
    },
    
    showModal(title, body, confirmText = 'Confirm') {
        $('#modalTitle').text(title);
        $('#modalBody').html(body);
        $('#modalConfirm').text(confirmText);
        $('#modal').addClass('active');
    },
    
    hideModal() {
        $('#modal').removeClass('active');
        this.currentAction = null;
        $('#modalConfirm').removeData('wage');
    },
    
    showDepositModal() {
        const body = `
            <div class="input-group">
                <label class="input-label">Amount to Deposit</label>
                <input type="number" class="input-field" id="depositAmount" placeholder="Enter amount" min="1" step="1">
            </div>
            <p style="color: var(--text-muted); font-size: 0.875rem;">
                Money will be taken from your cash and added to business funds.
            </p>
        `;
        this.showModal('Deposit Funds', body, 'Deposit');
        this.currentAction = 'deposit';
        
        // Focus en el input
        setTimeout(() => {
            $('#depositAmount').focus();
        }, 100);
    },
    
    showWithdrawModal() {
        const body = `
            <div class="input-group">
                <label class="input-label">Amount to Withdraw</label>
                <input type="number" class="input-field" id="withdrawAmount" placeholder="Enter amount" min="1" step="1">
            </div>
            <p style="color: var(--text-muted); font-size: 0.875rem;">
                Money will be taken from business funds and added to your cash.
            </p>
        `;
        this.showModal('Withdraw Funds', body, 'Withdraw');
        this.currentAction = 'withdraw';
        
        setTimeout(() => {
            $('#withdrawAmount').focus();
        }, 100);
    },
    
    showHireModal() {
        const grades = typeof BusinessAPI !== 'undefined' && typeof BusinessAPI.getGrades === 'function'
            ? BusinessAPI.getGrades()
            : [];
        const wageLimits = typeof BusinessAPI !== 'undefined' && BusinessAPI.wageLimits
            ? BusinessAPI.wageLimits
            : {};
        const wageMinCandidate = wageLimits && Number(wageLimits.min);
        const wageMaxCandidate = wageLimits && Number(wageLimits.max);
        const wageMin = Number.isFinite(wageMinCandidate) ? wageMinCandidate : 0;
        const wageMax = Number.isFinite(wageMaxCandidate) ? wageMaxCandidate : 10000;

        const gradeOptions = Array.isArray(grades) && grades.length > 0
            ? grades.map((grade) => {
                const label = grade.label || `Grade ${grade.value}`;
                return `<option value="${grade.value}">${label}</option>`;
            }).join('')
            : '<option value="0">Grade 0</option>';

        const body = `
            <div class="input-group">
                <label class="input-label">Player Selection</label>
                <div style="display: flex; gap: 0.5rem; margin-bottom: 0.75rem;">
                    <button type="button" class="btn btn-info" id="nearestPlayerBtn" style="flex: 1;">
                        <i class="fas fa-user-friends"></i>
                        <span>Nearest Player</span>
                    </button>
                    <button type="button" class="btn btn-secondary" id="manualPlayerBtn" style="flex: 1;">
                        <i class="fas fa-keyboard"></i>
                        <span>Manual ID</span>
                    </button>
                </div>
                <input type="number" class="input-field" id="playerId" placeholder="Enter player ID or use nearest player" min="1">
            </div>
            <div class="input-group">
                <label class="input-label">Grade Level</label>
                <select class="input-field" id="gradeLevel">
                    ${gradeOptions}
                </select>
            </div>
                <div class="input-group">
                    <label class="input-label">Hourly Wage</label>
                    <input type="number" class="input-field" id="hourlyWage" placeholder="Auto-assigned by grade" readonly style="opacity: 0.6; cursor: not-allowed;" min="${wageMin}" max="${wageMax}">
                    <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 0.25rem;">Wage is automatically set based on the selected grade (${wageMin}-${wageMax})</p>
                </div>
        `;
        this.showModal('Hire Employee', body, 'Hire');
        this.currentAction = 'hire';

        // Bind eventos para los botones
        setTimeout(() => {
            $('#nearestPlayerBtn').on('click', () => {
                this.getNearestPlayer();
            });

            $('#manualPlayerBtn').on('click', () => {
                $('#playerId').focus();
            });

            $('#playerId').focus();

            const updateWageDisplay = () => {
                const grade = parseInt($('#gradeLevel').val(), 10);
                const wage = typeof this.getWageForGrade === 'function' ? this.getWageForGrade(grade) : null;

                if (Number.isFinite(wage)) {
                    $('#hourlyWage').val(wage).data('wage', wage);
                    $('#modalConfirm').data('wage', wage);
                } else {
                    $('#hourlyWage').val('').data('wage', null);
                    $('#modalConfirm').data('wage', null);
                }
            };

            $('#gradeLevel').on('change', updateWageDisplay);
            updateWageDisplay();
        }, 100);
    },
    
    showEmployeesList() {
        if (typeof EmployeeManager !== 'undefined' && typeof EmployeeManager.showEmployeesList === 'function') {
            EmployeeManager.showEmployeesList();
            return;
        }

        // Fallback rápido en caso de que EmployeeManager no esté disponible
        const employees = typeof this.getSyncedEmployees === 'function'
            ? this.getSyncedEmployees()
            : [];
        let body = '<div class="employees-list">';

        if (employees.length === 0) {
            body += `
                <div style="
                    text-align: center;
                    padding: 2rem;
                    color: var(--text-muted);
                ">
                    <i class="fas fa-user-slash" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                    <p>No employees found</p>
                </div>
            `;
        } else {
            employees.forEach(emp => {
                body += `
                    <div class="employee-item" style="
                        background: rgba(51, 65, 85, 0.3);
                        border: 1px solid var(--border-color);
                        border-radius: 8px;
                        padding: 1rem;
                        margin-bottom: 0.75rem;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <div>
                            <div style="font-weight: 600; color: var(--text-primary);">${emp.name}</div>
                            <div style="color: var(--text-secondary); font-size: 0.875rem;">Grade ${emp.grade} • $${emp.wage}/hour</div>
                        </div>
                        <div style="display: flex; gap: 0.5rem;">
                            <button class="btn btn-info" style="padding: 0.5rem 1rem; font-size: 0.75rem;" onclick="BusinessManager.editEmployee(${emp.id})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-danger" style="padding: 0.5rem 1rem; font-size: 0.75rem;" onclick="BusinessManager.fireEmployee(${emp.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
        }

        body += '</div>';

        this.showModal('Manage Employees', body, 'Close');
        this.currentAction = 'manage';
    },
    
    handleModalConfirm() {
        switch(this.currentAction) {
            case 'deposit':
                this.handleDeposit();
                break;
            case 'withdraw':
                this.handleWithdraw();
                break;
            case 'hire':
                this.handleHire();
                break;
            case 'manage':
                this.hideModal();
                break;
        }
    },
    
    handleDeposit() {
        const amount = parseInt($('#depositAmount').val());
        
        // Validaciones de seguridad
        if (!amount || amount <= 0 || amount > 1000000 || !Number.isInteger(amount)) {
            this.showToast('Please enter a valid amount (1-1,000,000)', 'error');
            return;
        }
        
        // Simular depósito
        this.showToast(`Successfully deposited $${amount.toLocaleString()}`, 'success');
        this.updateFunds(45230 + amount);
        this.hideModal();
    },
    
    handleWithdraw() {
        const amount = parseInt($('#withdrawAmount').val());
        
        // Validaciones de seguridad
        if (!amount || amount <= 0 || amount > 1000000 || !Number.isInteger(amount)) {
            this.showToast('Please enter a valid amount (1-1,000,000)', 'error');
            return;
        }
        
        // Verificar fondos
        if (amount > 45230) {
            this.showToast('Insufficient business funds', 'error');
            return;
        }
        
        // Simular retiro
        this.showToast(`Successfully withdrew $${amount.toLocaleString()}`, 'success');
        this.updateFunds(45230 - amount);
        this.hideModal();
    },
    
    handleHire() {
        const playerId = parseInt($('#playerId').val());
        const grade = parseInt($('#gradeLevel').val());
        const wage = parseInt($('#hourlyWage').val());
        const wageLimits = typeof BusinessAPI !== 'undefined' && BusinessAPI.wageLimits
            ? BusinessAPI.wageLimits
            : {};
        const wageMinCandidate = wageLimits && Number(wageLimits.min);
        const wageMaxCandidate = wageLimits && Number(wageLimits.max);
        const wageMin = Number.isFinite(wageMinCandidate) ? wageMinCandidate : 0;
        const wageMax = Number.isFinite(wageMaxCandidate) ? wageMaxCandidate : 10000;
        const grades = typeof BusinessAPI !== 'undefined' && typeof BusinessAPI.getGrades === 'function'
            ? BusinessAPI.getGrades()
            : [];
        const gradeValues = grades.map(g => g.value);
        const minGrade = gradeValues.length > 0 ? Math.min(...gradeValues) : 0;
        const maxGrade = gradeValues.length > 0 ? Math.max(...gradeValues) : 0;

        // Validaciones de seguridad
        if (!playerId || !Number.isInteger(playerId) || playerId <= 0 || playerId > 9999) {
            this.showToast('Please enter a valid player ID (1-9999)', 'error');
            return;
        }

        if (!Number.isInteger(grade) || grade < minGrade || grade > maxGrade || (gradeValues.length > 0 && !gradeValues.includes(grade))) {
            this.showToast(`Invalid grade level (${minGrade}-${maxGrade})`, 'error');
            return;
        }

        if (!Number.isFinite(wage) || wage < wageMin || wage > wageMax) {
            this.showToast(`Invalid wage amount (${wageMin}-${wageMax})`, 'error');
            return;
        }

        // Simular contratación (wage será asignado automáticamente por el servidor)
        this.showToast(`Successfully hired player ${playerId} at grade ${grade}`, 'success');
        this.hideModal();
    },
    
    editEmployee(id) {
        this.showToast(`Edit employee ${id} - Feature coming soon`, 'info');
    },
    
    fireEmployee(id) {
        this.showToast(`Employee ${id} has been fired`, 'success');
    },
    
    updateFunds(newAmount) {
        $('#businessFunds').text(`$${newAmount.toLocaleString()}`);
    },
    
    showToast(message, type = 'info') {
        const toast = $(`
            <div class="toast ${type}">
                <i class="fas fa-${this.getToastIcon(type)}"></i>
                <span>${message}</span>
            </div>
        `);
        
        $('#toastContainer').append(toast);
        
        // Mostrar toast
        setTimeout(() => {
            toast.addClass('show');
        }, 100);
        
        // Ocultar después de 3 segundos
        setTimeout(() => {
            toast.removeClass('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 3000);
    },
    
    getToastIcon(type) {
        switch(type) {
            case 'success': return 'check-circle';
            case 'error': return 'exclamation-circle';
            case 'warning': return 'exclamation-triangle';
            case 'info': return 'info-circle';
            default: return 'info-circle';
        }
    },
    
    applyBusinessData(business = {}) {
        const jobLabel = business.jobLabel
            || business.job_label
            || (business.job && business.job.label)
            || business.job_name
            || business.jobName
            || 'Business';
        $('#jobTitle span').text(jobLabel);

        if (business.name) {
            $('#businessName').text(business.name);
        }

        if (Number.isFinite(business.funds)) {
            this.updateFunds(business.funds);
        } else if (typeof business.funds === 'string') {
            $('#businessFunds').text(business.funds);
        }

        const employeesFromState = typeof this.getSyncedEmployees === 'function'
            ? this.getSyncedEmployees()
            : [];
        const employees = Array.isArray(business.employees)
            ? business.employees
            : (Array.isArray(employeesFromState) ? employeesFromState : []);

        if (Array.isArray(business.employees) && typeof this.setSyncedEmployees === 'function') {
            this.setSyncedEmployees(business.employees);
        }

        if (typeof BusinessAPI !== 'undefined') {
            const previousBusiness = BusinessAPI.currentBusiness || {};
            BusinessAPI.currentBusiness = {
                ...previousBusiness,
                ...business,
                employees: Array.isArray(employees) ? [...employees] : (previousBusiness.employees || [])
            };
        }

        this.updateEmployeeCount(Array.isArray(employees) ? employees.length : 0);

        const userRole = $('#userRole');
        const roleBadge = userRole.find('.role-badge');
        const userName = userRole.find('.user-name');

        const roleFromData = (business.user && business.user.role)
            || business.role
            || (business.metadata && business.metadata.role)
            || (business.isBoss || business.is_boss || business.isboss ? 'boss' : null);
        const normalizedRole = roleFromData ? roleFromData.toString().toLowerCase() : null;

        roleBadge.removeClass('boss employee viewer');

        if (normalizedRole) {
            roleBadge.addClass(normalizedRole);
            roleBadge.text(normalizedRole.toUpperCase());
        } else {
            roleBadge.addClass('viewer');
            roleBadge.text('VIEWER');
        }

        if (business.user && business.user.name) {
            userName.text(business.user.name);
        } else if (business.userName) {
            userName.text(business.userName);
        } else if (business.user_name) {
            userName.text(business.user_name);
        }
    },

    getDefaultMockBusiness() {
        return {
            jobLabel: 'Police Department',
            jobName: 'police',
            name: 'Los Santos Police Department',
            funds: 45230,
            employees: [
                { id: 1, name: 'Jane Smith', citizenid: 'DEF67890', grade: 2, wage: 45 },
                { id: 2, name: 'Bob Johnson', citizenid: 'GHI01234', grade: 1, wage: 35 },
                { id: 3, name: 'Alice Brown', citizenid: 'JKL56789', grade: 3, wage: 55 }
            ],
            user: {
                name: 'John Doe',
                role: 'boss'
            }
        };
    },

    getWageForGrade(grade) {
        if (!Number.isInteger(grade) || typeof BusinessAPI === 'undefined' || typeof BusinessAPI.getGrades !== 'function') {
            return null;
        }

        const gradeInfo = BusinessAPI.getGrades().find(g => g.value === grade);
        return gradeInfo && Number.isFinite(gradeInfo.wage) ? gradeInfo.wage : null;
    },

    loadMockData() {
        if (typeof FiveMCallbacks !== 'undefined' && FiveMCallbacks.isFiveM) {
            return;
        }

        if (typeof MockData !== 'undefined' && MockData.isActive) {
            const business = MockData.getBusiness();
            if (business) {
                this.applyBusinessData(business);
                return;
            }
        }

        this.applyBusinessData(this.getDefaultMockBusiness());
    },
    
    getNearestPlayer() {
        // Simular obtención del jugador más cercano
        this.showLoading('Finding nearest player...');
        
        setTimeout(() => {
            this.hideLoading();
            
            // Simular jugador encontrado
            const nearestPlayerId = Math.floor(Math.random() * 100) + 1;
            $('#playerId').val(nearestPlayerId);
            
            this.showToast(`Found nearest player: ID ${nearestPlayerId}`, 'success');
        }, 1500);
    }
};

// Función global para testing (solo en modo desarrollo)
window.togglePanel = function() {
    // Solo permitir en modo desarrollo (navegador)
    if (typeof GetParentResourceName === 'undefined') {
        if (BusinessManager.isOpen) {
            BusinessManager.hidePanel();
        } else {
            BusinessManager.showPanel();
        }
    } else {
        console.warn('Testing function not available in FiveM environment');
    }
};
