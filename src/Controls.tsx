import { Button, Tooltip } from "@fluentui/react-components";
import type { ReactElement } from "react";
export function IconButton({
  label,
  icon,
  onClick,
  disabled = false,
}: {
  label: string;
  icon: ReactElement;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <Tooltip content={label} relationship="label">
      <Button
        appearance="subtle"
        size="small"
        aria-label={label}
        icon={icon}
        onClick={onClick}
        disabled={disabled}
      />
    </Tooltip>
  );
}
