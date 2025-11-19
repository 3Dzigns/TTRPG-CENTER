export interface UsageMeterProps {
    id?: string;
    label: string;
    value: number;
    quota: number;
    description?: string;
    disabled?: boolean;
    disabledReason?: string;
    className?: string;
}
export declare function UsageMeter({ id, label, value, quota, description, disabled, disabledReason, className }: UsageMeterProps): any;
