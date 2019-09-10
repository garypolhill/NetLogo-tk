#!/usr/bin/perl
#
# Module to read in CSV files

package csv;
require Exporter;

use strict;

our @ISA = qw(Exporter);
our @EXPORT = qw(read_csv, read_raw_csv);
our @EXPORT_OK = qw(split_csv);

sub read_raw_csv {
  my ($file, $ignore) = @_;

  $ignore = 0 if !defined($ignore);

  my @data;

  if($file !~ /\.csv$/i) {
    warn "File $file does not have a CSV suffix: ignoring\n";
    return @data;
  }
  
  open(FP, "<", $file) or die "Cannot read CSV file $file: $!\n";

  for(my $i = 0; $i < $ignore; $i++) {
    <FP>;
  }

  while(my $line = <FP>) {
    my @row = &split_csv($line);
    push(@data, \@row);
  }

  close(FP);
  
  return @data;
}

sub read_csv {
  my ($file, $ignore) = @_;

  $ignore = 0 if !defined($ignore);
  
  my @data;

  if($file !~ /\.csv$/i) {
    warn "File $file does not have a CSV suffix: ignoring\n";
    return @data;
  }
  
  open(FP, "<", $file) or die "Cannot read CSV file $file: $!\n";

  for(my $i = 0; $i < $ignore; $i++) {
    <FP>;
  }

  my $header_line = <FP>;
  $header_line =~ s/\s+$//;
  my @headers = &split_csv($header_line);

  while(my $line = <FP>) {
    $line =~ s/\s+$//;

    my @cells = &split_csv($line);

    my %row;
    for(my $i = 0; $i <= $#headers; $i++) {
      $row{$headers[$i]} = $cells[$i];
    }

    push(@data, \%row);
  }

  close(FP);

  return @data;
}

sub split_csv {
  my ($row) = @_;

  my @qc = split(/([,\"])/, $row);

  my @cells;

  my $state = 'start';
  my $concat = '';
  while(scalar(@qc) > 0) {
    my $symbol = shift(@qc);
    my $end = (scalar(@qc) == 0);

    next if $symbol eq "";

    if($state eq 'start') {
      if($symbol eq ",") {
	push(@cells, '');
	$state = 'blank';
      }
      elsif($symbol eq "\"") {
	$state = 'quote_cell';
      }
      else {
	push(@cells, $symbol);
	$state = 'plain';
      }
    }
    elsif($state eq 'plain') {
      if($symbol eq ",") {
	$state = 'next';
      }
      elsif($symbol eq "\"") {
	die "Quote encountered in unquoted cell\n";
      }
    }
    elsif($state eq 'blank') {
      push(@cells, '');
      if($symbol eq ",") {
      }
      elsif($symbol eq "\"") {
	$state = 'quote_cell';
      }
      else {
	push(@cells, $symbol);
	$state = 'plain';
      }
    }
    elsif($state eq 'quote_cell') {
      $concat = '';
      if($symbol eq "\"") {
	$state = 'quote';
      }
      else {
	$concat .= $symbol;
	$state = 'in_quote';
      }
    }
    elsif($state eq 'in_quote') {
      if($symbol eq "\"") {
	$state = 'quote';
	push(@cells, $concat) if($end);
      }
      else {
	$concat .= $symbol;
      }
    }
    elsif($state eq 'quote') {
      if($symbol eq "\"") {
	$concat .= $symbol;
	$state = 'in_quote';
	if($end) {
	  die "No close quote in quoted cell\n";
	}
      }
      elsif($symbol eq ",") {
	push(@cells, $concat);
	$state = 'next';
      }
      else {
	die "No close quote in quoted cell\n";
      }
    }
    elsif($state eq 'next') {
      if($symbol eq "\"") {
	$state = 'quote_cell';
      }
      elsif($symbol eq ",") {
	push(@cells, '');
	$state = 'blank';
      }
      else {
	push(@cells, $symbol);
	$state = 'plain';
      }
    }
    else {
      die "Unrecognized state \"$state\"\n";
    }
  }


  return @cells;
}

1;
