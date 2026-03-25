import { describe, it, expect } from 'vitest';
import { hasPermission, missingPermissions } from '../rbac';

describe('RBAC Utilities', () => {
  describe('hasPermission', () => {
    it('should return true when permission exists in user permissions', () => {
      const userPermissions = ['dashboard.view', 'tenant.manage', 'system.submit'];
      expect(hasPermission(userPermissions, 'dashboard.view')).toBe(true);
      expect(hasPermission(userPermissions, 'tenant.manage')).toBe(true);
      expect(hasPermission(userPermissions, 'system.submit')).toBe(true);
    });

    it('should return false when permission does not exist in user permissions', () => {
      const userPermissions = ['dashboard.view', 'tenant.manage'];
      expect(hasPermission(userPermissions, 'backup.manage')).toBe(false);
      expect(hasPermission(userPermissions, 'automation.manage')).toBe(false);
    });

    it('should return false when user permissions array is empty', () => {
      const userPermissions: string[] = [];
      expect(hasPermission(userPermissions, 'dashboard.view')).toBe(false);
    });

    it('should return false when user permissions is undefined', () => {
      const userPermissions = undefined;
      expect(hasPermission(userPermissions, 'dashboard.view')).toBe(false);
    });

    it('should return false when user permissions is null', () => {
      const userPermissions = null as any;
      expect(hasPermission(userPermissions, 'dashboard.view')).toBe(false);
    });

    it('should be case-sensitive', () => {
      const userPermissions = ['dashboard.view'];
      expect(hasPermission(userPermissions, 'Dashboard.View')).toBe(false);
      expect(hasPermission(userPermissions, 'dashboard.VIEW')).toBe(false);
    });

    it('should handle special characters in permission names', () => {
      const userPermissions = ['api.read', 'api.write', 'api.delete'];
      expect(hasPermission(userPermissions, 'api.read')).toBe(true);
      expect(hasPermission(userPermissions, 'api.execute')).toBe(false);
    });
  });

  describe('missingPermissions', () => {
    it('should return empty array when user has all required permissions', () => {
      const userPermissions = ['dashboard.view', 'tenant.manage', 'system.submit'];
      const required = ['dashboard.view', 'system.submit'];
      expect(missingPermissions(userPermissions, required)).toEqual([]);
    });

    it('should return array of missing permissions', () => {
      const userPermissions = ['dashboard.view'];
      const required = ['dashboard.view', 'tenant.manage', 'backup.manage'];
      const result = missingPermissions(userPermissions, required);
      expect(result).toContain('tenant.manage');
      expect(result).toContain('backup.manage');
      expect(result).not.toContain('dashboard.view');
    });

    it('should handle empty required permissions array', () => {
      const userPermissions = ['dashboard.view'];
      const required: string[] = [];
      expect(missingPermissions(userPermissions, required)).toEqual([]);
    });

    it('should handle undefined user permissions', () => {
      const userPermissions = undefined;
      const required = ['dashboard.view', 'tenant.manage'];
      expect(missingPermissions(userPermissions, required)).toEqual(required);
    });

    it('should handle null user permissions', () => {
      const userPermissions = null as any;
      const required = ['dashboard.view', 'tenant.manage'];
      expect(missingPermissions(userPermissions, required)).toEqual(required);
    });

    it('should return all required permissions when user has none', () => {
      const userPermissions: string[] = [];
      const required = ['dashboard.view', 'tenant.manage', 'backup.manage'];
      expect(missingPermissions(userPermissions, required)).toEqual(required);
    });

    it('should preserve order of missing permissions', () => {
      const userPermissions = ['system.submit'];
      const required = ['dashboard.view', 'tenant.manage', 'automation.manage', 'system.submit'];
      const missing = missingPermissions(userPermissions, required);
      expect(missing).toEqual(['dashboard.view', 'tenant.manage', 'automation.manage']);
    });

    it('should handle duplicate permissions in required array', () => {
      const userPermissions: string[] = [];
      const required = ['dashboard.view', 'dashboard.view', 'tenant.manage'];
      const missing = missingPermissions(userPermissions, required);
      // Both duplicates should be in the result
      expect(missing.filter(p => p === 'dashboard.view')).toHaveLength(2);
    });

    it('should be case-sensitive when checking missing permissions', () => {
      const userPermissions = ['dashboard.view'];
      const required = ['Dashboard.View', 'dashboard.view'];
      const missing = missingPermissions(userPermissions, required);
      expect(missing).toContain('Dashboard.View');
      expect(missing).not.toContain('dashboard.view');
    });
  });

  describe('Integration scenarios', () => {
    it('should correctly handle multi-permission checks for admin role', () => {
      const adminPermissions = [
        'dashboard.view',
        'tenant.manage',
        'system.submit',
        'backup.manage',
        'automation.manage',
      ];

      // Admin should have all permissions
      expect(hasPermission(adminPermissions, 'dashboard.view')).toBe(true);
      expect(hasPermission(adminPermissions, 'tenant.manage')).toBe(true);
      expect(hasPermission(adminPermissions, 'backup.manage')).toBe(true);

      // Check missing permissions (should be none)
      const missing = missingPermissions(adminPermissions, [
        'dashboard.view',
        'tenant.manage',
        'system.submit',
      ]);
      expect(missing).toEqual([]);
    });

    it('should correctly handle multi-permission checks for operator role', () => {
      const operatorPermissions = ['dashboard.view', 'system.submit', 'automation.manage'];

      // Operator should have system and automation permissions
      expect(hasPermission(operatorPermissions, 'system.submit')).toBe(true);
      expect(hasPermission(operatorPermissions, 'automation.manage')).toBe(true);

      // But not tenant management
      expect(hasPermission(operatorPermissions, 'tenant.manage')).toBe(false);

      // Check missing permissions
      const missing = missingPermissions(operatorPermissions, [
        'tenant.manage',
        'backup.manage',
      ]);
      expect(missing).toEqual(['tenant.manage', 'backup.manage']);
    });

    it('should correctly handle multi-permission checks for readonly role', () => {
      const readonlyPermissions = ['dashboard.view'];

      // Readonly should only have dashboard.view
      expect(hasPermission(readonlyPermissions, 'dashboard.view')).toBe(true);

      // But not management or operational permissions
      expect(hasPermission(readonlyPermissions, 'tenant.manage')).toBe(false);
      expect(hasPermission(readonlyPermissions, 'system.submit')).toBe(false);
      expect(hasPermission(readonlyPermissions, 'automation.manage')).toBe(false);

      // Check missing permissions for advanced operations
      const missing = missingPermissions(readonlyPermissions, [
        'system.submit',
        'automation.manage',
        'backup.manage',
      ]);
      expect(missing).toEqual(['system.submit', 'automation.manage', 'backup.manage']);
    });
  });
});
