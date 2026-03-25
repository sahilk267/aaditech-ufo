import { Controller, type FieldPath, type FieldValues, type UseFormReturn } from "react-hook-form";
import type { ReactNode } from "react";

interface FormInputProps<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> {
  form: UseFormReturn<TFieldValues>;
  name: TName;
  label?: string;
  placeholder?: string;
  type?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  maxLength?: number;
  min?: number;
  max?: number;
  step?: number;
  rows?: number;
  pattern?: string;
}

/**
 * FormInput Component
 * Integrates React Hook Form with error display and validation feedback
 */
export function FormInput<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>({
  form,
  name,
  label,
  placeholder,
  type = "text",
  required = false,
  disabled = false,
  helperText,
  maxLength,
  min,
  max,
  step,
  rows,
  pattern,
}: FormInputProps<TFieldValues, TName>) {
  const fieldState = form.getFieldState(name);
  const isError = !!fieldState.error;
  const isTextarea = rows !== undefined;

  return (
    <div className="form-field">
      {label && (
        <label htmlFor={String(name)} className="form-label">
          {label}
          {required && <span className="required-marker">*</span>}
        </label>
      )}
      <Controller
        name={name}
        control={form.control}
        render={({ field }) =>
          isTextarea ? (
            <textarea
              {...field}
              id={String(name)}
              placeholder={placeholder}
              disabled={disabled}
              rows={rows}
              maxLength={maxLength}
              className={`form-input ${isError ? "form-input--error" : ""}`}
            />
          ) : (
            <input
              {...field}
              id={String(name)}
              type={type}
              placeholder={placeholder}
              disabled={disabled}
              maxLength={maxLength}
              min={min}
              max={max}
              step={step}
              pattern={pattern}
              className={`form-input ${isError ? "form-input--error" : ""}`}
            />
          )
        }
      />
      {isError && (
        <span className="form-error">{fieldState.error?.message}</span>
      )}
      {helperText && !isError && (
        <small className="form-helper">{helperText}</small>
      )}
    </div>
  );
}

interface FormSelectProps<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> {
  form: UseFormReturn<TFieldValues>;
  name: TName;
  label?: string;
  placeholder?: string;
  options: Array<{ value: string | number; label: string }>;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
}

/**
 * FormSelect Component
 * Handles select/dropdown fields with React Hook Form
 */
export function FormSelect<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>({
  form,
  name,
  label,
  placeholder,
  options,
  required = false,
  disabled = false,
  helperText,
}: FormSelectProps<TFieldValues, TName>) {
  const fieldState = form.getFieldState(name);
  const isError = !!fieldState.error;

  return (
    <div className="form-field">
      {label && (
        <label htmlFor={String(name)} className="form-label">
          {label}
          {required && <span className="required-marker">*</span>}
        </label>
      )}
      <Controller
        name={name}
        control={form.control}
        render={({ field }) => (
          <select
            {...field}
            id={String(name)}
            disabled={disabled}
            className={`form-input form-select ${isError ? "form-input--error" : ""}`}
          >
            {placeholder && <option value="">{placeholder}</option>}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        )}
      />
      {isError && (
        <span className="form-error">{fieldState.error?.message}</span>
      )}
      {helperText && !isError && (
        <small className="form-helper">{helperText}</small>
      )}
    </div>
  );
}

interface FormCheckboxProps<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> {
  form: UseFormReturn<TFieldValues>;
  name: TName;
  label: ReactNode;
  helperText?: string;
  disabled?: boolean;
}

/**
 * FormCheckbox Component
 * Handles checkbox fields with React Hook Form
 */
export function FormCheckbox<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>({
  form,
  name,
  label,
  helperText,
  disabled = false,
}: FormCheckboxProps<TFieldValues, TName>) {
  const fieldState = form.getFieldState(name);
  const isError = !!fieldState.error;

  return (
    <div className="form-field form-field--checkbox">
      <Controller
        name={name}
        control={form.control}
        render={({ field }) => (
          <label className="form-checkbox-label">
            <input
              {...field}
              type="checkbox"
              checked={field.value === true}
              disabled={disabled}
              className={`form-checkbox ${isError ? "form-checkbox--error" : ""}`}
            />
            <span>{label}</span>
          </label>
        )}
      />
      {isError && (
        <span className="form-error">{fieldState.error?.message}</span>
      )}
      {helperText && !isError && (
        <small className="form-helper">{helperText}</small>
      )}
    </div>
  );
}

interface FormFileInputProps<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> {
  form: UseFormReturn<TFieldValues>;
  name: TName;
  label?: string;
  accept?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
}

/**
 * FormFileInput Component
 * Handles file upload fields with React Hook Form
 */
export function FormFileInput<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>({
  form,
  name,
  label,
  accept,
  required = false,
  disabled = false,
  helperText,
}: FormFileInputProps<TFieldValues, TName>) {
  const fieldState = form.getFieldState(name);
  const isError = !!fieldState.error;

  return (
    <div className="form-field">
      {label && (
        <label htmlFor={String(name)} className="form-label">
          {label}
          {required && <span className="required-marker">*</span>}
        </label>
      )}
      <Controller
        name={name}
        control={form.control}
        render={({ field: { onChange } }) => (
          <input
            id={String(name)}
            type="file"
            accept={accept}
            disabled={disabled}
            onChange={(e) => {
              const file = e.target.files?.[0];
              onChange(file);
            }}
            className={`form-input form-file-input ${isError ? "form-input--error" : ""}`}
          />
        )}
      />
      {isError && (
        <span className="form-error">{fieldState.error?.message}</span>
      )}
      {helperText && !isError && (
        <small className="form-helper">{helperText}</small>
      )}
    </div>
  );
}

interface FormSubmitButtonProps {
  isLoading?: boolean;
  isDisabled?: boolean;
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger";
}

/**
 * FormSubmitButton Component
 * Styled submit button with loading state
 */
export function FormSubmitButton({
  isLoading = false,
  isDisabled = false,
  children,
  variant = "primary",
}: FormSubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={isLoading || isDisabled}
      className={`button button--${variant} ${isLoading ? "button--loading" : ""}`}
    >
      {isLoading ? "Processing..." : children}
    </button>
  );
}
