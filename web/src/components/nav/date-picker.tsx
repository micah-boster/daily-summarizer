"use client";

import { useState } from "react";
import { CalendarIcon } from "lucide-react";
import { parseISO } from "date-fns";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";

interface DatePickerProps {
  availableDates: string[];
  selectedDate: string | null;
  onSelect: (date: string) => void;
}

export function DatePicker({
  availableDates,
  selectedDate,
  onSelect,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);

  const availableDateObjects = availableDates.map((d) => parseISO(d));
  const selectedDateObject = selectedDate ? parseISO(selectedDate) : undefined;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        aria-label="Open date picker"
      >
        <CalendarIcon className="h-4 w-4" />
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selectedDateObject}
          onSelect={(date) => {
            if (date) {
              const iso = date.toISOString().split("T")[0];
              onSelect(iso);
              setOpen(false);
            }
          }}
          modifiers={{
            available: availableDateObjects,
          }}
          modifiersClassNames={{
            available:
              "relative after:absolute after:bottom-0.5 after:left-1/2 after:-translate-x-1/2 after:h-1 after:w-1 after:rounded-full after:bg-primary",
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
