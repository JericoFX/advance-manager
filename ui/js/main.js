$(document).ready(function() {
    // Inicializar la aplicación
    BusinessManager.init();
});

const BusinessManager = {
    isOpen: false,
    
    init() {
        this.bindEvents();
        this.showPanel(); // Para testing en navegador
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
                    <option value="0">Grade 0 - Cadet</option>
                    <option value="1">Grade 1 - Officer</option>
                    <option value="2">Grade 2 - Sergeant</option>
                    <option value="3">Grade 3 - Lieutenant</option>
                    <option value="4">Grade 4 - Captain</option>
                </select>
            </div>
                <div class="input-group">
                    <label class="input-label">Hourly Wage</label>
                    <input type="number" class="input-field" id="hourlyWage" placeholder="Auto-assigned by grade" readonly style="opacity: 0.6; cursor: not-allowed;">
                    <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 0.25rem;">Wage is automatically set based on grade from QBCore shared</p>
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
                }
            };

            $('#gradeLevel').on('change', updateWageDisplay);
            updateWageDisplay();
        }, 100);
    },
    
    showEmployeesList() {
        // Simular lista de empleados
        const employees = [
            { id: 1, name: 'Jane Smith', grade: 2, wage: 45 },
            { id: 2, name: 'Bob Johnson', grade: 1, wage: 35 },
            { id: 3, name: 'Alice Brown', grade: 3, wage: 55 }
        ];
        
        let body = '<div class="employees-list">';
        
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
        
        // Validaciones de seguridad
        if (!playerId || !Number.isInteger(playerId) || playerId <= 0 || playerId > 9999) {
            this.showToast('Please enter a valid player ID (1-9999)', 'error');
            return;
        }
        
        if (grade < 0 || grade > 4 || !Number.isInteger(grade)) {
            this.showToast('Invalid grade level (0-4)', 'error');
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
    
    loadMockData() {
        // Simular datos de prueba
        $('#jobTitle span').text('Police Department');
        $('#businessName').text('Los Santos Police Department');
        $('#businessFunds').text('$45,230');
        $('#totalEmployees').text('8');
        
        // Simular rol de usuario
        const userRole = $('#userRole');
        userRole.find('.role-badge').addClass('boss').text('BOSS');
        userRole.find('.user-name').text('John Doe');
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
