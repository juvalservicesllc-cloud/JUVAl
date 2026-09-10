import {test,expect} from 'vitest';
import {t,setLanguage,matches} from '../src/i18n';
test('Spanish presentation handles labels, dynamic metadata and original evidence fallback',()=>{
 setLanguage('es');
 expect(t('PHASE 09')).toBe('FASE 09');
 expect(t('Run 2026-09-10; commit abc123')).toBe('Ejecución 2026-09-10; commit abc123');
 expect(t('30 days')).toBe('30 días');
 expect(matches('Roadmap','hoja')).toBe(true);
 expect(t('VERIFIED_CODE')).toBe('CÓDIGO VERIFICADO');
 expect(t('src/juval/domain/product.py')).toBe('src/juval/domain/product.py');
 setLanguage('en');expect(t('Roadmap')).toBe('Roadmap');
});
