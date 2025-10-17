// Funciones específicas para el manejo de negocios
const BusinessAPI = {
    // Tabla de salarios por grado (simulado desde el servidor)
    wagesByGrade: [25, 35, 45, 55, 75],

    // Simular datos del negocio
    currentBusiness: {
        id: 1,
        name: 'Los Santos Police Department',
        jobName: 'police',
        funds: 45230,
        owner: 'ABC12345',
        employees: [
            { id: 1, name: 'Jane Smith', citizenid: 'DEF67890', grade: 2, wage: 45 },
            { id: 2, name: 'Bob Johnson', citizenid: 'GHI01234', grade: 1, wage: 35 },
            { id: 3, name: 'Alice Brown', citizenid: 'JKL56789', grade: 3, wage: 55 }
        ]
    },
    
    // Obtener información del negocio
    getBusinessInfo() {
        return new Promise((resolve) => {
            // Simular delay de API
            setTimeout(() => {
                resolve(this.currentBusiness);
            }, 500);
        });
    },
    
    // Depositar fondos
    depositFunds(amount) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                if (amount <= 0) {
                    reject({ error: 'Invalid amount' });
                    return;
                }
                
                // Simular verificación de dinero del jugador
                const playerCash = 10000; // Simular dinero del jugador
                
                if (amount > playerCash) {
                    reject({ error: 'Insufficient funds' });
                    return;
                }
                
                this.currentBusiness.funds += amount;
                resolve({ 
                    success: true, 
                    message: `Successfully deposited $${amount.toLocaleString()}`,
                    newBalance: this.currentBusiness.funds
                });
            }, 1000);
        });
    },
    
    // Retirar fondos
    withdrawFunds(amount) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                if (amount <= 0) {
                    reject({ error: 'Invalid amount' });
                    return;
                }
                
                if (amount > this.currentBusiness.funds) {
                    reject({ error: 'Insufficient business funds' });
                    return;
                }
                
                this.currentBusiness.funds -= amount;
                resolve({ 
                    success: true, 
                    message: `Successfully withdrew $${amount.toLocaleString()}`,
                    newBalance: this.currentBusiness.funds
                });
            }, 1000);
        });
    },
    
    // Contratar empleado
    hireEmployee(playerId, grade) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                // Simular verificación de jugador
                const playerNames = ['Mike Wilson', 'Sarah Connor', 'Tom Hardy', 'Emma Stone'];
                const randomName = playerNames[Math.floor(Math.random() * playerNames.length)];
                
                if (!playerId || playerId <= 0) {
                    reject({ error: 'Invalid player ID' });
                    return;
                }
                
                if (grade < 0 || grade > 4) {
                    reject({ error: 'Invalid grade level' });
                    return;
                }
                
                // Simular wage según el grade (esto vendría del servidor)
                const assignedWage = this.getWageForGrade(grade);

                if (!Number.isInteger(assignedWage)) {
                    reject({ error: 'Invalid wage for grade' });
                    return;
                }
                
                const newEmployee = {
                    id: this.currentBusiness.employees.length + 1,
                    name: randomName,
                    citizenid: `CID${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
                    grade: grade,
                    wage: assignedWage
                };
                
                this.currentBusiness.employees.push(newEmployee);
                
                resolve({ 
                    success: true, 
                    message: `Successfully hired ${randomName} at grade ${grade}`,
                    employee: newEmployee
                });
            }, 1500);
        });
    },
    
    // Despedir empleado
    fireEmployee(employeeId) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                const employeeIndex = this.currentBusiness.employees.findIndex(emp => emp.id === employeeId);
                
                if (employeeIndex === -1) {
                    reject({ error: 'Employee not found' });
                    return;
                }
                
                const employee = this.currentBusiness.employees[employeeIndex];
                this.currentBusiness.employees.splice(employeeIndex, 1);
                
                resolve({ 
                    success: true, 
                    message: `${employee.name} has been fired`,
                    employee: employee
                });
            }, 1000);
        });
    },
    
    // Actualizar salario de empleado
    updateEmployeeWage(employeeId, newWage) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                const employee = this.currentBusiness.employees.find(emp => emp.id === employeeId);
                
                if (!employee) {
                    reject({ error: 'Employee not found' });
                    return;
                }
                
                if (newWage < 10 || newWage > 100) {
                    reject({ error: 'Invalid wage amount' });
                    return;
                }
                
                employee.wage = newWage;
                
                resolve({ 
                    success: true, 
                    message: `Updated ${employee.name}'s wage to $${newWage}/hour`,
                    employee: employee
                });
            }, 1000);
        });
    },
    
    // Actualizar grado de empleado
    updateEmployeeGrade(employeeId, newGrade) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                const employee = this.currentBusiness.employees.find(emp => emp.id === employeeId);
                
                if (!employee) {
                    reject({ error: 'Employee not found' });
                    return;
                }
                
                if (newGrade < 0 || newGrade > 4) {
                    reject({ error: 'Invalid grade level' });
                    return;
                }
                
                employee.grade = newGrade;
                
                resolve({ 
                    success: true, 
                    message: `Updated ${employee.name}'s grade to ${newGrade}`,
                    employee: employee
                });
            }, 1000);
        });
    },
    
    // Obtener empleados
    getEmployees() {
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve(this.currentBusiness.employees);
            }, 500);
        });
    },
    
    // Obtener grados disponibles
    getGrades() {
        return [
            { value: 0, label: 'Grade 0 - Cadet' },
            { value: 1, label: 'Grade 1 - Officer' },
            { value: 2, label: 'Grade 2 - Sergeant' },
            { value: 3, label: 'Grade 3 - Lieutenant' },
            { value: 4, label: 'Grade 4 - Captain' }
        ];
    },

    // Obtener sueldo por grado
    getWageForGrade(grade) {
        const wage = this.wagesByGrade[grade];
        return Number.isInteger(wage) ? wage : null;
    },
    
    // Formatear dinero
    formatMoney(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    },
    
    // Obtener nombre del grado
    getGradeName(grade) {
        const grades = this.getGrades();
        const gradeInfo = grades.find(g => g.value === grade);
        return gradeInfo ? gradeInfo.label : `Grade ${grade}`;
    }
};

// Extender BusinessManager con funciones API
if (typeof BusinessManager !== 'undefined') {
    Object.assign(BusinessManager, {
        // Sobrescribir funciones para usar API simulada
        async handleDeposit() {
            const amount = parseInt($('#depositAmount').val());
            if (!amount || amount <= 0) {
                this.showToast('Please enter a valid amount', 'error');
                return;
            }
            
            try {
                this.showLoading('Processing deposit...');
                const result = await BusinessAPI.depositFunds(amount);
                this.hideLoading();
                
                this.showToast(result.message, 'success');
                this.updateFunds(result.newBalance);
                this.hideModal();
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to deposit funds', 'error');
            }
        },
        
        async handleWithdraw() {
            const amount = parseInt($('#withdrawAmount').val());
            if (!amount || amount <= 0) {
                this.showToast('Please enter a valid amount', 'error');
                return;
            }
            
            try {
                this.showLoading('Processing withdrawal...');
                const result = await BusinessAPI.withdrawFunds(amount);
                this.hideLoading();
                
                this.showToast(result.message, 'success');
                this.updateFunds(result.newBalance);
                this.hideModal();
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to withdraw funds', 'error');
            }
        },
        
        async handleHire() {
            const playerId = parseInt($('#playerId').val());
            const grade = parseInt($('#gradeLevel').val());
            
            if (!playerId) {
                this.showToast('Please enter a player ID', 'error');
                return;
            }
            
            try {
                this.showLoading('Hiring employee...');
                const result = await BusinessAPI.hireEmployee(playerId, grade);
                this.hideLoading();
                
                this.showToast(result.message, 'success');
                this.updateEmployeeCount();
                this.hideModal();
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to hire employee', 'error');
            }
        },
        
        async fireEmployee(id) {
            try {
                this.showLoading('Firing employee...');
                const result = await BusinessAPI.fireEmployee(id);
                this.hideLoading();
                
                this.showToast(result.message, 'success');
                this.updateEmployeeCount();
                
                // Actualizar lista si está abierta
                if (this.currentAction === 'manage') {
                    this.showEmployeesList();
                }
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to fire employee', 'error');
            }
        },
        
        updateEmployeeCount() {
            $('#totalEmployees').text(BusinessAPI.currentBusiness.employees.length);
        },
        
        showLoading(message) {
            // Crear overlay de carga
            const loader = $(`
                <div class="loading-overlay" style="
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 9999;
                ">
                    <div style="
                        background: var(--bg-secondary);
                        border: 1px solid var(--border-color);
                        border-radius: 12px;
                        padding: 2rem;
                        display: flex;
                        align-items: center;
                        gap: 1rem;
                        color: var(--text-primary);
                    ">
                        <i class="fas fa-spinner fa-spin" style="font-size: 1.5rem; color: var(--primary-color);"></i>
                        <span>${message}</span>
                    </div>
                </div>
            `);
            
            $('body').append(loader);
        },
        
        hideLoading() {
            $('.loading-overlay').remove();
        }
    });
}
