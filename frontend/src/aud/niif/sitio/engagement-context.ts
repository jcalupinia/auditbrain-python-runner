import {z} from 'zod';
import {HttpError} from './audit-store';
export const commonFields={
 country:z.string().trim().min(2).max(80),currency:z.string().trim().regex(/^[A-Z]{3}$/),
 visit:z.enum(['Preliminar','Final']),edition:z.string().trim().min(2).max(180),
 adoption:z.string().trim().max(1000).default(''),reuseScope:z.enum(['all','selected','one']).default('one'),
 // Se pregunta en la ficha y no por prueba: define si el encargo habilita las
 // cédulas de impuesto diferido. Para Ecuador el deterioro a valor neto de
 // realización de inventarios está en la lista cerrada del Reglamento.
 deferredTax:z.boolean().default(false),
};
export const engagementFields=z.object({
 client:z.string().trim().min(2).max(200),ruc:z.string().trim().min(3).max(40),activity:z.string().trim().min(2).max(200),
 year:z.coerce.number().int().min(2000).max(2100),cutoff:z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine(s=>!isNaN(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s),
 preparer:z.string().trim().min(2).max(150),reviewer:z.string().trim().min(2).max(150),firm:z.enum(['Audit Consulting','Partner']),
 framework:z.enum(['NIIF completas','NIIF para las PYMES']),
 ...Object.fromEntries(Object.entries(commonFields).map(([k,v])=>[k,v.optional()])),
 // Se declara después del mapeo a .optional() para que nunca quede indefinida:
 // la ficha debe decir sí o no, no callar.
 deferredTax:z.boolean().default(false),
});
export const contextEditSchema=engagementFields.extend(commonFields);
export function parseEngagement(value:unknown,full=false){const result=(full?contextEditSchema:engagementFields).safeParse(value);if(!result.success)throw new HttpError(400,'Complete cliente, responsables, firma, marco, país, moneda, visita, edición y fecha válidos.');const d:any=result.data;if(Number(d.cutoff.slice(0,4))!==d.year)throw new HttpError(400,'La fecha de corte debe corresponder al ejercicio.');if(d.country==='Ecuador'&&!/^\d{13}$/.test(d.ruc))throw new HttpError(400,'Para Ecuador, indique un RUC de 13 dígitos.');return d;}
