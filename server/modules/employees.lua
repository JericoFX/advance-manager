local Employees = {}
local Business = require 'server.modules.business'

function Employees.Hire(businessId, citizenId, grade, wage)
    local business = Business.GetById(businessId)
    if not business then
        return false, 'Business not found'
    end
    
    local jobInfo = Business.GetJobInfo(business.job_name)
    if not jobInfo then
        return false, 'Job not found'
    end
    
    if not jobInfo.grades[tostring(grade)] then
        return false, 'Invalid grade'
    end
    
    -- Check if already employed
    local existing = MySQL.query.await('SELECT id FROM business_employees WHERE business_id = ? AND citizenid = ?', {businessId, citizenId})
    if existing and existing[1] then
        return false, 'Employee already hired'
    end
    
    -- Set job for player
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if Player then
        Player.Functions.SetJob(business.job_name, grade)
    end
    
    -- Add to database
    local result = MySQL.insert.await([[
        INSERT INTO business_employees (business_id, citizenid, grade, wage)
        VALUES (?, ?, ?, ?)
    ]], {businessId, citizenId, grade, wage})
    
    if result then
        return true, 'Employee hired successfully'
    else
        return false, 'Failed to hire employee'
    end
end

function Employees.Fire(businessId, citizenId)
    local business = Business.GetById(businessId)
    if not business then
        return false, 'Business not found'
    end
    
    -- Set job to unemployed
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if Player then
        Player.Functions.SetJob('unemployed', 0)
    end
    
    -- Remove from database
    local result = MySQL.update.await('DELETE FROM business_employees WHERE business_id = ? AND citizenid = ?', {businessId, citizenId})
    
    if result > 0 then
        return true, 'Employee fired successfully'
    else
        return false, 'Employee not found'
    end
end

function Employees.GetAll(businessId)
    local result = MySQL.query.await([[
        SELECT be.*, p.charinfo
        FROM business_employees be
        LEFT JOIN players p ON p.citizenid = be.citizenid
        WHERE be.business_id = ?
    ]], {businessId})
    
    local employees = {}
    if result then
        for _, employee in pairs(result) do
            local charinfo = json.decode(employee.charinfo or '{}')
            table.insert(employees, {
                id = employee.id,
                citizenid = employee.citizenid,
                grade = employee.grade,
                wage = employee.wage,
                name = charinfo.firstname .. ' ' .. charinfo.lastname
            })
        end
    end
    
    return employees
end

function Employees.UpdateWage(businessId, citizenId, newWage)
    local result = MySQL.update.await([[
        UPDATE business_employees 
        SET wage = ? 
        WHERE business_id = ? AND citizenid = ?
    ]], {newWage, businessId, citizenId})
    
    return result > 0
end

function Employees.UpdateGrade(businessId, citizenId, newGrade)
    local business = Business.GetById(businessId)
    if not business then
        return false, 'Business not found'
    end
    
    local jobInfo = Business.GetJobInfo(business.job_name)
    if not jobInfo or not jobInfo.grades[tostring(newGrade)] then
        return false, 'Invalid grade'
    end
    
    -- Update player job grade
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if Player then
        Player.Functions.SetJob(business.job_name, newGrade)
    end
    
    -- Update database
    local result = MySQL.update.await([[
        UPDATE business_employees 
        SET grade = ? 
        WHERE business_id = ? AND citizenid = ?
    ]], {newGrade, businessId, citizenId})
    
    return result > 0
end

return Employees
