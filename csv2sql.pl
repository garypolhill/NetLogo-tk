#!/usr/bin/perl
#
# Convert CSV to SQL

use FindBin;
use lib $FindBin::Bin;

use csv_parser;

use strict;

my $DB;
my $tablespace;
my $netlogo = 0;
my $merge_table;
my $MAX_BOOL_CHAR = 8;	# Big enough for true/false and to be a power of two
my $MAX_INT_CHAR = 32;		# Big enough for a +/- long which will have 19
my $MAX_REAL_CHAR = 64;		# Big enough for a quad double +-X.30chrE+-5chr

while($ARGV[0] =~ /^-/) {
  my $opt = shift(@ARGV);

  if($opt eq "-db") {
    $DB = shift(@ARGV);
  }
  elsif($opt eq "-tablespace") {
    $tablespace = shift(@ARGV);
  }
  elsif($opt eq "-netlogo-table") {
    $netlogo = 6;
  }
  elsif($opt eq "-merge") {
    $merge_table = shift(@ARGV);
  }
  else {
    die "Option not recognized $opt\n";
  }
}

if(scalar(@ARGV) < 2) {
  die "Usage: $0 [-db <database name>] [-tablespace <tablespace name>]\n",
    "\t[-netlogo-table] <SQL file> <CSV files...>\n";
}

my ($sql_file, @csv_files) = @ARGV;

if($sql_file !~ /\.sql/i) {
  die "SQL file $sql_file must have a .sql suffix\n";
}

open(SQL, ">", $sql_file) or die "Cannot create SQL file $sql_file: $!\n";

if(defined($DB)) {
  print SQL "create database \'$DB\';\n";
}

if(defined($tablespace)) {
  print SQL "create tablespace \'$tablespace\';\n";
}

my $file_no = 0;
my %types;
my @all_keys;

foreach my $csv_file (@csv_files) {
  $file_no++;
  my @data = csv::read_csv($csv_file, $netlogo);

  my $table_name = (defined($merge_table) ? $merge_table : $csv_file);
  $table_name =~ s/\.csv$//i;
  $table_name = &to_sql_var($table_name);

  if(!defined($merge_table) || $file_no == 1) {
    print SQL "create table if not exists $table_name (\n";

    %types = &check_sql_types(\@data);

    @all_keys = sort { $a cmp $b } keys(%types);

    for(my $i = 0; $i <= $#all_keys; $i++) {
      print SQL "  ", &to_sql_var($all_keys[$i]), " ", $types{$all_keys[$i]};
      print SQL "," if $i < $#all_keys;
      print SQL "\n";
    }

    print SQL ");\n";
  }

  foreach my $datum (@data) {
    print SQL "insert into $table_name (";
    my @keys = sort { $a cmp $b } keys %$datum;
    print SQL join(", ", @keys), ") VALUES (";
    for(my $i = 0; $i <= $#keys; $i++) {
      if(!defined($types{$keys[$i]})) {
	die "Field $keys[$i] in file $csv_files[$file_no - 1] is not present ",
	  "in file $csv_files[0]: merge failed\n";
      }
      print SQL ", " if $i > 0;
      if($types{$keys[$i]} =~ /^varchar/) {
	print SQL "\'$$datum{$keys[$i]}\'";
      }
      else {
	print SQL $$datum{$keys[$i]};
      }
    }
    print SQL ");\n";
  }
}

print SQL "commit;\n";
close(SQL);

exit 0;

sub check_sql_types {
  my ($data) = @_;

  my %data_types;

  foreach my $datum (@$data) {
    foreach my $key (keys(%$datum)) {
      my $value = $$datum{$key};

      my $value_type = &sql_type($value);

      if(!defined($data_types{$key})) {
	$data_types{$key} = $value_type;
      }
      else {
	$data_types{$key} = &promote($value_type, $data_types{$key});
      }
    }
  }

  return %data_types;
}

# VARCHAR(len)
# INTEGER
# REAL
# BOOLEAN
# DATE yyyy-mm-dd
# TIME hh:mm:ss
# TIMESTAMP

sub sql_type {
  my ($value) = @_;

  if($value eq "true" || $value eq "false"
     || $value eq "TRUE" || $value eq "FALSE"
     || $value eq "t" || $value eq "f"
     || $value eq "T" || $value eq "F") {
    return "boolean";
  }
  elsif($value =~ /^[+-]?\d+$/) {
    return "integer";
  }
  elsif($value =~ /^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$/) {
    return "real";
  }
  else {
    my $l = length($value);
    my $l2 = 1;
    while($l2 < $l) {
      $l2 *= 2;
      if($l2 >= 2 ** 20) {
	die "Seriously long string ($l chars)\n";
      }
    }
    return "varchar($l2)";
  }
}

sub promote {
  my ($type1, $type2) = @_;

  return $type1 if $type1 eq $type2;

  if($type1 eq "boolean") {
    if($type2 =~ /^varchar\((\d+)\)$/) {
      my $n = $1;
      if($n < $MAX_BOOL_CHAR) {
	return "varchar($MAX_BOOL_CHAR)";
      }
    }
    return $type2;
  }
  if($type1 eq "integer") {
    return $type1 if $type2 eq "boolean" or $type2 eq "integer";
    return $type2 if $type2 eq "real";
    if($type2 =~ /^varchar\((\d+)\)$/) {
      my $n = $1;
      if($n < $MAX_INT_CHAR) {
	return "varchar($MAX_INT_CHAR)";
      }
    }
    return $type2;
  }
  if($type1 eq "real") {
    if($type2 eq "boolean" || $type2 eq "integer" || $type2 eq "real") {
      return $type1;
    }
    if($type2 =~ /^varchar\((\d+)\)$/) {
      my $n = $1;
      if($n < $MAX_REAL_CHAR) {
	return "varchar($MAX_REAL_CHAR)";
      }
    }
    return $type2;    
  }
  if($type1 =~ /^varchar\((\d+)\)$/) {
    my $n = $1;
    if($type2=~ /^varchar\((\d+)\)$/) {
      my $m = $1;
      return ($m > $n) ? $type2 : $type1;
    }
  }
  die "Unrecognized type $type1 or $type2\n";
}

sub to_sql_var {
  my ($word) = @_;

  $word =~ s/\W/_/g;

  return $word;
}
