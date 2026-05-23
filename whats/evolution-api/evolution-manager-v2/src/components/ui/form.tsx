import * as LabelPrimitive from "@radix-ui/react-label";
import { Slot } from "@radix-ui/react-slot";
import * as React from "react";
import { Controller, ControllerProps, FieldPath, FieldValues, FormProvider, useFormContext } from "react-hook-form";
import { WithContext as ReactTags, SEPARATORS } from "react-tag-input";

import { Label } from "@/components/ui/label";

import { cn } from "@/lib/utils";

import { defaultInputClassNames } from "./input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";
import { Switch } from "./switch";

const Form = FormProvider;

type FormFieldContextValue<TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>> = {
  name: TName;
};

const FormFieldContext = React.createContext<FormFieldContextValue>({} as FormFieldContextValue);

const FormField = <TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>({ ...props }: ControllerProps<TFieldValues, TName>) => {
  return (
    <FormFieldContext.Provider value={{ name: props.name }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  );
};

const useFormField = () => {
  const fieldContext = React.useContext(FormFieldContext);
  const itemContext = React.useContext(FormItemContext);
  const { getFieldState, formState } = useFormContext();

  const fieldState = getFieldState(fieldContext.name, formState);

  if (!fieldContext) {
    throw new Error("useFormField should be used within <FormField>");
  }

  const { id } = itemContext;

  return {
    id,
    name: fieldContext.name,
    formItemId: `${id}-form-item`,
    formDescriptionId: `${id}-form-item-description`,
    formMessageId: `${id}-form-item-message`,
    ...fieldState,
  };
};

type FormItemContextValue = {
  id: string;
};

const FormItemContext = React.createContext<FormItemContextValue>({} as FormItemContextValue);

const FormItem = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => {
  const id = React.useId();

  return (
    <FormItemContext.Provider value={{ id }}>
      <div ref={ref} className={cn("space-y-2", className)} {...props} />
    </FormItemContext.Provider>
  );
});
FormItem.displayName = "FormItem";

const FormLabel = React.forwardRef<React.ElementRef<typeof LabelPrimitive.Root>, React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>>(({ className, ...props }, ref) => {
  const { error, formItemId } = useFormField();

  return <Label ref={ref} className={cn(error && "text-rose-600", className)} htmlFor={formItemId} {...props} />;
});
FormLabel.displayName = "FormLabel";

const FormControl = React.forwardRef<React.ElementRef<typeof Slot>, React.ComponentPropsWithoutRef<typeof Slot>>(({ ...props }, ref) => {
  const { error, formItemId, formDescriptionId, formMessageId } = useFormField();

  return <Slot ref={ref} id={formItemId} aria-describedby={!error ? `${formDescriptionId}` : `${formDescriptionId} ${formMessageId}`} aria-invalid={!!error} {...props} />;
});
FormControl.displayName = "FormControl";

const FormDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({ className, ...props }, ref) => {
  const { formDescriptionId } = useFormField();

  return <p ref={ref} id={formDescriptionId} className={cn("text-sm text-muted-foreground", className)} {...props} />;
});
FormDescription.displayName = "FormDescription";

const FormMessage = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({ className, children, ...props }, ref) => {
  const { error, formMessageId } = useFormField();
  const body = error ? String(error?.message) : children;

  if (!body) {
    return null;
  }

  return (
    <p ref={ref} id={formMessageId} className={cn("text-sm font-medium text-rose-600", className)} {...props}>
      {body}
    </p>
  );
});
FormMessage.displayName = "FormMessage";

const FormInput = <TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>({
  name,
  label,
  children,
  required,
  readOnly,
  className,
  ...props
}: Omit<ControllerProps<TFieldValues, TName>, "render"> & {
  label?: string;
  children: React.ReactNode;
  className?: string;
  required?: boolean;
  readOnly?: boolean;
}) => {
  return (
    <FormField
      {...props}
      name={name}
      render={({ field }) => (
        <FormItem className={className}>
          {label && (
            <FormLabel>
              {label}
              {required && <span className="ml-2 text-rose-600">*</span>}
            </FormLabel>
          )}
          <FormControl>
            {React.isValidElement(children) &&
              React.cloneElement(children as any, {
                // eslint-disable-line
                ...field,
                value: field.value ?? "",
                required,
                readOnly,
                checked: field.value,
                onCheckedChange: field.onChange,
              })}
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

const FormSwitch = <TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>({
  name,
  label,
  required,
  className,
  helper,
  reverse,
  ...props
}: Omit<ControllerProps<TFieldValues, TName>, "render"> & {
  label?: string;
  helper?: string;
  className?: string;
  required?: boolean;
  reverse?: boolean;
}) => {
  return (
    <FormField
      {...props}
      name={name}
      render={({ field }) => (
        <FormItem className={cn("flex items-center gap-3", reverse && "flex-row-reverse justify-end", className)}>
          <div className="flex flex-col gap-2">
            {label && (
              <FormLabel>
                <p className="break-all">
                  {label}
                  {required && <span className="ml-2 text-rose-600">*</span>}
                </p>
                {helper && <FormDescription className="mt-2">{helper}</FormDescription>}
              </FormLabel>
            )}
          </div>
          <FormControl>
            <Switch checked={field.value} onCheckedChange={field.onChange} required={required} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

const FormSelect = <TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>({
  name,
  label,
  helper,
  required,
  options,
  placeholder,
  disabled,
  ...props
}: Omit<ControllerProps<TFieldValues, TName>, "render"> & {
  label?: string;
  required?: boolean;
  helper?: string;
  placeholder?: string;
  disabled?: boolean;
  options: { value: string; label: string }[];
}) => {
  return (
    <FormField
      {...props}
      name={name}
      render={({ field }) => (
        <FormItem>
          {label && (
            <FormLabel>
              {label}
              {required && <span className="ml-2 text-rose-600">*</span>}
            </FormLabel>
          )}
          <FormControl>
            <Select onValueChange={field.onChange} defaultValue={field.value} disabled={disabled}>
              <FormControl>
                <SelectTrigger>
                  <SelectValue placeholder={placeholder} />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                {options.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormControl>
          {helper && <FormDescription>{helper}</FormDescription>}
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

const FormTags = <TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>({
  name,
  label,
  helper,
  required,
  placeholder,
  ...props
}: Omit<ControllerProps<TFieldValues, TName>, "render"> & {
  label?: string;
  required?: boolean;
  helper?: string;
  placeholder?: string;
}) => {
  return (
    <FormField
      {...props}
      name={name}
      render={({ field }) => {
        let tags: string[] = [];
        if (Array.isArray(field.value)) tags = field.value;

        return (
          <FormItem>
            {label && (
              <FormLabel>
                {label}
                {required && <span className="ml-2 text-rose-600">*</span>}
              </FormLabel>
            )}
            <FormControl>
              <ReactTags
                tags={tags.map((tag) => ({
                  id: tag,
                  text: tag,
                  className: "",
                }))}
                handleDelete={(tagIndex) => field.onChange(tags.filter((_t, idx) => idx !== tagIndex))}
                handleAddition={(tag) => field.onChange([...tags, tag.id])}
                inputFieldPosition="bottom"
                placeholder={placeholder}
                autoFocus={false}
                allowDragDrop={false}
                separators={[SEPARATORS.ENTER, SEPARATORS.TAB, SEPARATORS.COMMA]}
                classNames={{
                  tags: "tagsClass",
                  tagInput: "tagInputClass",
                  tagInputField: defaultInputClassNames,
                  selected: "my-2 flex flex-wrap gap-2",
                  tag: "flex items-center gap-2 px-2 py-1 bg-primary/30 rounded-md text-xs",
                  remove: "[&>svg]:fill-rose-600 hover:[&>svg]:fill-rose-700",
                  suggestions: "suggestionsClass",
                  activeSuggestion: "activeSuggestionClass",
                  editTagInput: "editTagInputClass",
                  editTagInputField: "editTagInputFieldClass",
                  clearAll: "clearAllClass",
                }}
              />
            </FormControl>
            {helper && <FormDescription>{helper}</FormDescription>}
            <FormMessage />
          </FormItem>
        );
      }}
    />
  );
};

export { useFormField, Form, FormItem, FormLabel, FormControl, FormDescription, FormMessage, FormField, FormInput, FormSelect, FormSwitch, FormTags };
