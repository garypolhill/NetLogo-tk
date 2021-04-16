#!/usr/bin/perl
#
# csv-merger.pl
#
# Program to merge CSV files. NAs are entered in cells for which there are
# no data.
#
# Usage: ./csv-merger.pl [-pattern <regexp>] [-quiet] [-NA <str>] [-same]
#             [-modified <days ago>] [-since <YYYY-MM-DD>] <output file>
#             [<CSV files or dirs...>]
#
# If the -pattern <regexp> option is given, then the arguments should be
# directories to look in rather than CSV files. The reason the option is given
# is to provide for cases where the number of CSV files to merge is too many
# for the command line.
#
# The -quiet option shuts the script up -- it normally spits out information
# about how compatible all the CSV files are.
#
# The -NA option allows user configuration of the string to use for empty cells.
#
# The -same option will enforce that every file must have the same header line
# as whichever the first file is that is read.
#
# The -modified option allows you to specify a number of days ago since which
# the files to be checked must have been modified,
#
# The -since option does the same as -modified, but allows you to specify a
# date rather than a number of datys ago.
#
# Gary Polhill 22 April 2019
#
# Copyright (C) 2019  The James Hutton Institute
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>

use strict;
use Time::Local;

# Globals

my $NA = 'NA';
my $pattern = 0;
my $use_pattern = 0;
my $quiet = 0;
my $allow_diff = 1;
my $mod_days = 0;

# Process command-line options and check usage

while($ARGV[0] =~ /^-/) {
  my $option = shift(@ARGV);
  if($option eq '-NA') {
    $NA = shift(@ARGV);
  }
  elsif($option eq '-quiet') {
    $quiet = 1;
  }
  elsif($option eq '-pattern') {
    $use_pattern = 1;
    my $regex = shift(@ARGV);
    $pattern = qr/$regex/;
  }
  elsif($option eq '-same') {
    $allow_diff = 0;
  }
  elsif($option eq '-modified') {
    $mod_days = shift(@ARGV);
  }
  elsif($option eq '-since') {
    my $date = shift(@ARGV);
    my ($year, $month, $mday) = split(/-/, $date);

    my $time = timelocal(0, 0, 0, $mday, $month - 1, $year - 1900);
    $mod_days = (time - $time) / 86400;
  }
  else {
    die "Option $option not recognized\n";
  }
}

if(scalar(@ARGV) < 2) {
  die "Usage: $0 [-pattern <perl regexp>] [-quiet] [-NA <empty cell string>] ",
    "[-same] [-modified <days ago>] [-since <YYYY-MM-DD>] <Output CSV file> ",
    "<CSV files or dirs if -pattern given...>\n";
}

my $output = shift(@ARGV);

my @input;

if($use_pattern) {
  foreach my $dir (@ARGV) {
    opendir(DIR, $dir);
    foreach my $file (readdir(DIR)) {
      next if -z "$dir/$file";
      if($mod_days > 0 && -M "$dir/$file" > $mod_days) {
	next;
      }
      if($file =~ $pattern) {
	push(@input, "$dir/$file");
      }
#      else {
#	print "$file does not match $pattern\n" if !$quiet;
#      }
    }
    closedir(DIR);
  }
}
else {
  @input = @ARGV;
}

# Merge the CSVs...

my @headers;
my %header_count;
my $unheaded = 0;
my @data;			# This could get very big...

foreach my $file (@input) {
  if(!$quiet && $file !~ /\.csv$/i) {
    warn "Input file $file doesn't have a suffix indicating it's a CSV file\n";
  }
  open(IN, "<", $file) or die "Cannot read input CSV file $file: $!\n";

  my $header_line = <IN>;
  $header_line =~ s/\s+$//;

  my @this_headers = &parse_csv_line($header_line);

  # Keep track of the headers we've encountered
  
  foreach my $this_header (@this_headers) {
    if(!defined($header_count{$this_header})) {
      $header_count{$this_header} = 1;
      if(!$quiet) {
	print "Input file $file introduces new column heading $this_header\n";
      }
      if(!$allow_diff && $file ne $input[0]) {
	die "Input file $file has a column heading $this_header not in the ",
	  "first input file $input[0]\n";
      }
      push(@headers, $this_header);
    }
    else {
      $header_count{$this_header}++;
    }
  }
  if(!$allow_diff && $file ne $input[0]) {
    my %my_headers;
    foreach my $this_header (@this_headers) {
      $my_headers{$this_header} = 1;
    }
    foreach my $header (@headers) {
      if(!defined($my_headers{$header})) {
	die "Input file $file does not have column heading $header that ",
	  "appears in the first input file $input[0]\n";
      }
    }
  }

  # Read in the data
  
  my $nlines = 0;

  while(my $line = <IN>) {
    $line =~ s/\s+$//;
    $nlines++;
    my @entry = &parse_csv_line($line);

    if(!$quiet && (scalar(@entry) != scalar(@this_headers))) {
      warn "Input file $file, row $nlines has ", scalar(@entry), " cells ",
	"but ", scalar(@this_headers), " column headings\n";
    }

    my %datum;

    for(my $i = 0; $i <= $#this_headers && scalar(@entry) > 0; $i++) {
      $datum{$this_headers[$i]} = shift(@entry);
    }

    # If there are fewer entries than headers above, then the missing data
    # will be written as NAs later. The loop below saves the entries not
    # given a header.

    while(scalar(@entry) > 0) {
      if(!$allow_diff) {
	die "Input file $file has data without a column heading, so cannot ",
	  "be sure that all files have the same headings\n";
      }
      $unheaded++;
      my $unheader = "noheading$unheaded";
      if(defined($header_count{$unheader})) {
	die "Unheaded column in $file with a previous file having the name ",
	  "I was going to give this one ($unheader)\n";
      }
      if(!$quiet) {
	print "Adding new heading $unheader for data entry with no column ",
	  "heading in $file\n";
      }
      $header_count{$unheader} = 1;
      push(@headers, $unheader);
      push(@this_headers, $unheader);
      $datum{$unheader} = shift(@entry);
    }

    # Add the data from this row to the merged data to write later
    push(@data, \%datum);
  }

  if(!$quiet) {
    print "Added $nlines rows of data from $file\n";
  }
  
  close(IN);
}

# Do some reporting -- did all the files have the same header, and how many
# rows of data did we read?

if(!$quiet) {
  my $all_same = 1;
  my $count = 0;

  foreach my $n (values(%header_count)) {
    if($count == 0) {
      $count = $n;
    }
    elsif($count != $n) {
      $all_same = 0;
      last;
    }
  }

  if($all_same) {
    print "All files had the same header line\n";
  }
  else {
    print "The files had different header lines. Summary follows:\n";
    foreach my $header (@headers) {
      print "\t$header: $header_count{$header} files\n";
    }
  }

  print "Collected ", scalar(@data), " rows of data from ", scalar(@input),
    " files\n";
}

# Print out the merged CSV

open(CSV, ">", $output) or die "Cannot create output CSV file $output: $!\n";
print CSV join(",", @headers), "\n";
foreach my $datum (@data) {
  my $first = 1;
  foreach my $header (@headers) {
    if($first) {
      $first = 0;
    }
    else {
      print CSV ",";
    }
    if(defined($$datum{$header})) {
      print CSV $$datum{$header};
    }
    else {
      print CSV $NA;
    }
  }
  print CSV "\n";
}
close(CSV);

exit 0;

# Subroutines

# parse_csv_line
#
# Take a line of CSV data and parse it to cope with commas contained within
# cells. This is done a bit lazily -- any comma in double quotes is going to
# be assumed to be in a cell, even if the cell doesn't start and end with
# quotes.

sub parse_csv_line {
  my ($line) = @_;

  my @parts = split(/([\",])/, $line);

  my $cell = "";
  my @cells;
  my $in_quote = 0;
  foreach my $part (@parts) {
    if($part eq "\"") {
      $in_quote = $in_quote ? 0 : 1;
      $cell .= $part;
    }
    elsif($part eq ",") {
      if($in_quote) {
	$cell .= $part;
      }
      else {
	push(@cells, $cell);
	$cell = "";
      }
    }
    else {
      $cell .= $part;
    }
  }
  push(@cells, $cell) if $cell =~ /\S/;

  return @cells;
}
